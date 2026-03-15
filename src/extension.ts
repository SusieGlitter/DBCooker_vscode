import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import * as cp from 'child_process';
import * as yaml from 'js-yaml';
import { confirmChanges, discardChanges, showDiff, reapplyDecorations } from './diffHelper';

export let commentController: vscode.CommentController;
export let outputChannel: vscode.OutputChannel;

import * as dgram from 'dgram';

export function activate(context: vscode.ExtensionContext) {
    commentController = vscode.comments.createCommentController('cppHelper', 'Append Helper');
    outputChannel = vscode.window.createOutputChannel('DBCooker Diff');
    const chatProvider = new DBCookerChatProvider(context.extensionPath);
    
    // 启动插件级的 UDP 监听器
    const server = dgram.createSocket('udp4');
    server.on('message', (msg, rinfo) => {
        const raw = msg.toString().trim();
        const lines = raw.split('\n');

        lines.forEach(line => {
            const trimmedLine = line.trim();
            if (!trimmedLine) return;

            try {
                const parsed = JSON.parse(trimmedLine);
                // Log every message to output channel for debugging
                outputChannel.appendLine(`[UDP] Received ${parsed.category || 'unknown'}: ${trimmedLine}`);
                console.log(`[UDP] Received ${parsed.category || 'unknown'}: ${trimmedLine}`);

                // 如果是日志类 JSON，也同步到日志区
                if (parsed.category === 'log' && parsed.data?.message) {
                    chatProvider.postToWebview({ type: 'logUpdate', message: `[UDP] ${parsed.data.message}` });
                }
                // 结构化数据统一发往对话区
                chatProvider.postToWebview({ 
                    type: 'agentReply', 
                    message: trimmedLine 
                });

                // 如果收到 completed 状态的消息，触发文件检查
                if (parsed.category === 'step' && parsed.data?.state === 'completed') {
                    outputChannel.appendLine(`[${new Date().toLocaleTimeString()}] Step ${parsed.data.step_number} completed. Triggering check...`);
                    console.log(`[${new Date().toLocaleTimeString()}] Step ${parsed.data.step_number} completed. Triggering check...`);
                    chatProvider.triggerCheckForChanges();
                }
            } catch (e) {
                // 非 JSON 消息直接发往对话区
                outputChannel.appendLine(`[UDP] Received Non-JSON: ${trimmedLine}`);
                chatProvider.postToWebview({ 
                    type: 'agentReply', 
                    message: trimmedLine 
                });
            }
        });
    });
    server.bind(9999, '127.0.0.1');

    context.subscriptions.push({ dispose: () => server.close() });
    context.subscriptions.push(commentController);

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(DBCookerChatProvider.viewType, chatProvider)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('cppHelper.confirm', async (uriStr?: string) => {
            if (uriStr) await confirmChanges(uriStr);
        }),
        vscode.commands.registerCommand('cppHelper.discard', async (uriStr?: string) => {
            if (uriStr) await discardChanges(uriStr);
        }),
        vscode.window.onDidChangeActiveTextEditor(editor => {
            if (editor) {
                reapplyDecorations(editor);
            }
        }),
        vscode.commands.registerCommand('pythonBridge.showLogs', () => {
            LogPanel.createOrShow(context.extensionPath, chatProvider.getLogs());
        }),
        vscode.commands.registerCommand('pythonBridge.start', () => {
            vscode.commands.executeCommand('dbcooker.chatView.focus');
            chatProvider.clearChat();
        })
    );
}

class DBCookerChatProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'dbcooker.chatView';
    private _view?: vscode.WebviewView;
    private _currentProcess: cp.ChildProcess | undefined;
    private _isKilledByUser: boolean = false;
    private _logs: string[] = [];
    private _messageBuffer: any[] = []; // 消息缓冲区
    private _isSavingHistory = false;
    private _lastCompileFolder: string = '';
    private _lastBackupFolder: string = '';
    private _hasInitialBackup: boolean = false;

    private _pendingClear = false;

    constructor(private readonly _extensionPath: string) {}

    public clearChat() {
        this._pendingClear = true;
        if (this._view) {
            this._view.webview.postMessage({ type: 'clearChat' });
            this._pendingClear = false;
        }
    }

    public postToWebview(message: any) {
        if (this._view) {
            this._view.webview.postMessage(message);
        } else {
            // 如果 Webview 没准备好，存入缓冲区
            this._messageBuffer.push(message);
        }
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [vscode.Uri.file(path.join(this._extensionPath, 'src', 'web'))]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.type) {
                case 'executeScript':
                    await this._runPythonScript(message.data);
                    break;
                case 'stopScript':
                    this._stopScript();
                    break;
                case 'showLogs':
                    vscode.commands.executeCommand('pythonBridge.showLogs');
                    break;
                case 'webviewReady':
                    console.log(`[Extension] Webview is ready.`);
                    outputChannel.appendLine(`[Extension] Webview is ready.`);
                    if (this._pendingClear) {
                        this._view?.webview.postMessage({ type: 'clearChat' });
                        this._pendingClear = false;
                    }
                    // 同步缓冲区中的消息
                    if (this._messageBuffer.length > 0) {
                        this._messageBuffer.forEach(msg => {
                            this._view?.webview.postMessage(msg);
                        });
                        this._messageBuffer = [];
                    }
                    // If a process is running, sync the logs to the new webview
                    if (this._currentProcess) {
                        this._logs.forEach(line => {
                            const isSerial = line.startsWith('[SERIAL]');
                            if (isSerial) {
                                const serialContent = line.replace('[SERIAL]', '').trim();
                                this._view?.webview.postMessage({ type: 'agentReply', message: serialContent });
                            } else {
                                this._view?.webview.postMessage({ type: 'logUpdate', message: line });
                            }
                        });
                    }
                    await this._sendHistory();
                    break;
                case 'confirmDiff':
                    await vscode.commands.executeCommand('cppHelper.confirm', vscode.Uri.file(message.filePath).toString());
                    break;
                case 'discardDiff':
                    await vscode.commands.executeCommand('cppHelper.discard', vscode.Uri.file(message.filePath).toString());
                    break;
                case 'openFile':
                    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(message.filePath));
                    await vscode.window.showTextDocument(doc, { preview: false });
                    break;
            }
        });
    }

    private async _sendHistory() {
        try {
            const historyPath = path.join(this._extensionPath, 'log', 'history.json');
            if (fs.existsSync(historyPath)) {
                const data = await fs.promises.readFile(historyPath, 'utf8');
                const history = JSON.parse(data);
                this._view?.webview.postMessage({ type: 'loadHistory', data: history });
            }
        } catch (e) {
            console.error("Failed to load history", e);
        }
    }

    private async _saveHistory(currentLogGroup: any) {
        if (this._isSavingHistory) return;
        this._isSavingHistory = true;
        try {
            const logDir = path.join(this._extensionPath, 'log');
            const historyPath = path.join(logDir, 'history.json');
            if (!fs.existsSync(logDir)) {
                fs.mkdirSync(logDir, { recursive: true });
            }
            let history = [];
            if (fs.existsSync(historyPath)) {
                const data = await fs.promises.readFile(historyPath, 'utf8');
                history = JSON.parse(data);
            }
            // Remove any existing entry with same timestamp to avoid duplicates
            history = history.filter((h: any) => h.timestamp !== currentLogGroup.timestamp);
            history.forEach((h: any) => h.isActive = false);
            history.push(currentLogGroup);
            await fs.promises.writeFile(historyPath, JSON.stringify(history, null, 2), 'utf8');
        } catch (e) {
            console.error("Failed to save history", e);
        } finally {
            this._isSavingHistory = false;
        }
    }

    public getLogs() {
        return this._logs;
    }

    public triggerCheckForChanges() {
        outputChannel.show(true); // Ensure the output channel is visible
        if (this._lastCompileFolder && this._lastBackupFolder) {
            const msg = `[${new Date().toLocaleTimeString()}] Triggering diff check... (Compile: ${this._lastCompileFolder}, Backup: ${this._lastBackupFolder})`;
            outputChannel.appendLine(msg);
            console.log(msg);
            this._checkForChanges(this._lastCompileFolder, this._lastBackupFolder);
        } else {
            const msg = `[${new Date().toLocaleTimeString()}] Skip diff check (folders not set).`;
            outputChannel.appendLine(msg);
            console.log(msg);
        }
    }

    private _stopScript() {
        if (this._currentProcess) {
            this._isKilledByUser = true;
            // 使用 SIGKILL 强制立即终止
            this._currentProcess.kill('SIGKILL');
            this._currentProcess = undefined;
            vscode.window.showInformationMessage('Pipeline terminated immediately.');
        }
    }

    private async _runPythonScript(inputData: any) {
        try {
            // Use the bundled venv python if available, otherwise fallback to system python
            let pythonPath = 'python';
            const venvPythonPath = path.join(this._extensionPath, 'venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
            
            if (fs.existsSync(venvPythonPath)) {
                pythonPath = venvPythonPath;
                outputChannel.appendLine(`[Extension] Using bundled Python venv: ${pythonPath}`);
            } else {
                outputChannel.appendLine(`[Extension] Bundled venv not found at ${venvPythonPath}, using system python.`);
            }

            const scriptPath = path.join(this._extensionPath, 'src', 'py', 'DBCode', 'agent_main.py');
            
            this._logs = []; // Clear current logs
            this._isKilledByUser = false;
            this._hasInitialBackup = false; // Reset for new run
            this._lastCompileFolder = '';
            this._lastBackupFolder = '';

            const currentLogGroup = {
                timestamp: new Date().toLocaleString(),
                messages: [] as string[],
                isActive: true,
                input: inputData // Store input for history
            };

            const pythonProcess = cp.spawn(pythonPath, [scriptPath], {
                env: { ...process.env, COLUMNS: '300', EXTENSION_PATH: this._extensionPath },
                cwd: path.join(this._extensionPath, 'src', 'py', 'DBCode')
            });
            this._currentProcess = pythonProcess;

            let outputData = '';
            let stdoutBuffer = '';

            const saveHistoryDebounced = () => {
                this._saveHistory(currentLogGroup);
            };

            pythonProcess.stdout.on('data', (data) => {
                const text = data.toString();
                outputData += text;
                stdoutBuffer += text;
                let nIndex;
                while ((nIndex = stdoutBuffer.indexOf('\n')) !== -1) {
                    const line = stdoutBuffer.substring(0, nIndex);
                    stdoutBuffer = stdoutBuffer.substring(nIndex + 1);
                    
                    // 脚本的标准输出（包含 Rich 表格）全部发往日志区
                    this._view?.webview.postMessage({ type: 'logUpdate', message: line });
                    
                    this._logs.push(line);
                    currentLogGroup.messages.push(line);
                    saveHistoryDebounced();

                    const compileMatch = line.match(/['"]?compile_folder['"]?\s*[:=]\s*(?:['"]([^'"]+)['"]|([^\s,}]+))/);
                    const backupMatch = line.match(/['"]?backup_folder['"]?\s*[:=]\s*(?:['"]([^'"]+)['"]|([^\s,}]+))/);
                    
                    if (compileMatch) {
                        this._lastCompileFolder = compileMatch[1] || compileMatch[2];
                        outputChannel.appendLine(`[${new Date().toLocaleTimeString()}] Detected Compile Folder: ${this._lastCompileFolder}`);
                    }
                    if (backupMatch) {
                        this._lastBackupFolder = backupMatch[1] || backupMatch[2];
                        outputChannel.appendLine(`[${new Date().toLocaleTimeString()}] Detected Backup Folder: ${this._lastBackupFolder}`);
                    }

                    if (this._lastCompileFolder && this._lastBackupFolder && !this._hasInitialBackup) {
                        try {
                            if (!fs.existsSync(this._lastBackupFolder)) {
                                cp.execSync(`rm -rf "${this._lastBackupFolder}" && cp -r "${this._lastCompileFolder}" "${this._lastBackupFolder}"`);
                                outputChannel.appendLine(`[${new Date().toLocaleTimeString()}] Initial backup created: ${this._lastCompileFolder} -> ${this._lastBackupFolder}`);
                            } else {
                                outputChannel.appendLine(`[${new Date().toLocaleTimeString()}] Using existing backup: ${this._lastBackupFolder}`);
                            }
                            this._hasInitialBackup = true;
                        } catch (e) {
                            outputChannel.appendLine(`[ERROR] Failed to create initial backup: ${e}`);
                        }
                    }
                }
            });

            pythonProcess.stderr.on('data', (data) => {
                const line = data.toString();
                this._logs.push(`[STDERR] ${line}`);
                currentLogGroup.messages.push(`[STDERR] ${line}`);
                saveHistoryDebounced();
            });

            pythonProcess.on('close', async (code) => {
                this._currentProcess = undefined;
                currentLogGroup.isActive = false;
                await this._saveHistory(currentLogGroup);

                if (this._isKilledByUser) {
                    this._view?.webview.postMessage({ type: 'stopped', message: 'Stopped by user.' });
                } else {
                    this._view?.webview.postMessage({ type: 'finished', code });
                }
                // Refresh history in webview
                await this._sendHistory();
            });

            pythonProcess.stdin.write(JSON.stringify(inputData));
            pythonProcess.stdin.end();

        } catch (err: any) {
            vscode.window.showErrorMessage(`Error: ${err.message}`);
        }
    }

    private async _checkForChanges(compileFolder: string, backupFolder: string) {
        try {
            const output = cp.execSync(`diff -rq "${backupFolder}" "${compileFolder}" || true`).toString();
            outputChannel.appendLine(`[${new Date().toLocaleTimeString()}] Diff command output:\n${output}`);
            console.log(`[${new Date().toLocaleTimeString()}] Diff command output:\n${output}`);
            const lines = output.split('\n');
            let changesFound = false;
            for (const line of lines) {
                if (line.startsWith('Files ') && line.includes(' and ') && line.endsWith(' differ')) {
                    const match = line.match(/Files (.*) and (.*) differ/);
                    if (match) {
                        changesFound = true;
                        const backupPath = match[1];
                        const compilePath = match[2];
                        outputChannel.appendLine(`  Found difference: ${compilePath}`);
                        console.log(`  Found difference: ${compilePath}`);
                        await showDiff(compilePath, backupPath, commentController);
                        // Notify webview about the modified file
                        this._view?.webview.postMessage({ type: 'agentReply', message: `Modified file: ${compilePath}` });
                    }
                }
            }
            if (!changesFound) {
                outputChannel.appendLine(`  No differences found.`);
                console.log(`  No differences found.`);
            }
        } catch (e: any) {
            outputChannel.appendLine(`[ERROR] Failed to run diff: ${e.message}`);
            console.error(`[ERROR] Failed to run diff: ${e.message}`);
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        const htmlPath = path.join(this._extensionPath, 'src', 'web', 'index.html');
        return fs.readFileSync(htmlPath, 'utf8');
    }
}

class LogPanel {
    public static currentPanel: LogPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];

    public static createOrShow(extensionPath: string, logs: string[]) {
        if (LogPanel.currentPanel) {
            LogPanel.currentPanel._updateLogs(logs);
            LogPanel.currentPanel._panel.reveal(vscode.ViewColumn.Two);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'dbcookerLogs',
            'DBCooker Logs',
            vscode.ViewColumn.Two,
            { enableScripts: true }
        );

        LogPanel.currentPanel = new LogPanel(panel, logs);
    }

    private constructor(panel: vscode.WebviewPanel, logs: string[]) {
        this._panel = panel;
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._updateLogs(logs);
    }

    private _updateLogs(logs: string[]) {
        this._panel.webview.html = `
            <html>
                <body style="background: #1e1e1e; color: #d4d4d4; font-family: monospace; padding: 10px;">
                    <h3>Execution Logs</h3>
                    <pre id="log-container">${logs.join('\n')}</pre>
                    <script>
                        window.addEventListener('message', event => {
                            if (event.data.type === 'updateLogs') {
                                document.getElementById('log-container').innerText = event.data.logs.join('\\n');
                            }
                        });
                    </script>
                </body>
            </html>
        `;
    }

    public dispose() {
        LogPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) x.dispose();
        }
    }
}