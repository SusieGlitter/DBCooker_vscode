import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import * as cp from 'child_process';
import * as yaml from 'js-yaml';

// Define the shape of the configuration we save
interface AppConfig {
    apiKey: string;
    timestamp: string;
}

export function activate(context: vscode.ExtensionContext) {
    const disposable = vscode.commands.registerCommand('pythonBridge.start', () => {
        PythonBridgePanel.createOrShow(context.extensionPath);
		
		vscode.window.showInformationMessage('WebView Panel Opened!');
    });

    context.subscriptions.push(disposable);
}

class PythonBridgePanel {
    public static currentPanel: PythonBridgePanel | undefined;
    public static readonly viewType = 'pythonBridge';

    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionPath: string;
    private _disposables: vscode.Disposable[] = [];

    public static createOrShow(extensionPath: string) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (PythonBridgePanel.currentPanel) {
            PythonBridgePanel.currentPanel._panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            PythonBridgePanel.viewType,
            'DBCooker Demo',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                localResourceRoots: [vscode.Uri.file(path.join(extensionPath, 'src', 'web'))],
                retainContextWhenHidden: true
            }
        );

        PythonBridgePanel.currentPanel = new PythonBridgePanel(panel, extensionPath);
    }

    private constructor(panel: vscode.WebviewPanel, extensionPath: string) {
        this._panel = panel;
        this._extensionPath = extensionPath;

        // Set the webview's initial html content
        this._panel.webview.html = this._getHtmlForWebview(this._panel.webview);

        // Listen for when the panel is disposed
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        // Handle messages from the webview
        this._panel.webview.onDidReceiveMessage(
            async (message) => {
                // DEBUG: Confirm message receipt
                vscode.window.showInformationMessage(`[Extension] Received Message Type: ${message.type}`);
                
                switch (message.type) {
                    case 'executeScript':
                        await this._runPythonScript(message.data);
                        return;
                }
            },
            null,
            this._disposables
        );
    }

    private async _runPythonScript(inputData: any) {
        try {
            // 1. Get Configuration
            const config = vscode.workspace.getConfiguration('pythonBridge');
            const apiKey = config.get<string>('apiKey') || '';
            const pythonPath = config.get<string>('pythonPath') || 'python';

            // --- DEBUG POPUPS ---
            const dataPreview = JSON.stringify(inputData).substring(0, 100) + "...";
            vscode.window.showInformationMessage(`[Extension] API Key: ${apiKey ? '***' + apiKey.slice(-4) : 'Not Set'}`);
            vscode.window.showInformationMessage(`[Extension] Payload: ${dataPreview}`);
            vscode.window.showInformationMessage(`[Extension] Executing: ${pythonPath}`);
            // --------------------

            // 2. Write Configuration to YAML
            const yamlConfig: AppConfig = {
                apiKey: apiKey,
                timestamp: new Date().toISOString()
            };

            const tempDir = os.tmpdir();
            const configFilePath = path.join(tempDir, `vscode_py_bridge_config_${Date.now()}.yaml`);
            const yamlStr = yaml.dump(yamlConfig);

            await fs.promises.writeFile(configFilePath, yamlStr, 'utf8');

            // 3. Prepare Python Script Path
            const scriptPath = path.join(this._extensionPath, 'src', 'py', 'main.py');

            // 4. Spawn Python Process
            const pythonProcess = cp.spawn(pythonPath, [scriptPath, '--config', configFilePath]);

            let outputData = '';
            let errorData = '';

            pythonProcess.stdout.on('data', (data) => {
                outputData += data.toString();
            });

            pythonProcess.stderr.on('data', (data) => {
                errorData += data.toString();
            });

            // Critical: Handle spawn errors (e.g., python not found)
            pythonProcess.on('error', (err) => {
                vscode.window.showErrorMessage(`Failed to start Python process: ${err.message}. Check 'pythonBridge.pythonPath' setting.`);
                this._panel.webview.postMessage({ type: 'error', message: `Spawn Error: ${err.message}` });
                fs.unlink(configFilePath, () => {});
            });

            pythonProcess.on('close', (code) => {
                // Clean up config file
                fs.unlink(configFilePath, () => {});

                // DEBUG
                vscode.window.showInformationMessage(`[Extension] Python exited with code: ${code}`);

                if (code !== 0) {
                    vscode.window.showErrorMessage(`Python script failed. Exit code ${code}`);
                    const msg = errorData || `Process exited with code ${code}`;
                    this._panel.webview.postMessage({ type: 'error', message: msg });
                } else {
                    try {
                        if (!outputData.trim()) {
                            throw new Error("Python script returned empty output.");
                        }

                        const jsonResult = JSON.parse(outputData);
                        // Send result back to Webview
                        this._panel.webview.postMessage({ type: 'result', data: jsonResult });
                        
                        vscode.window.showInformationMessage(`[Extension] Success: Sent result to Webview.`);

                    } catch (e: any) {
                        vscode.window.showErrorMessage(`Failed to parse Python output: ${e.message}`);
                        console.error("Python Output:", outputData); 
                        this._panel.webview.postMessage({ type: 'error', message: `Invalid JSON: ${e.message}. \nRaw Output: ${outputData}` });
                    }
                }
            });

            // 5. Send JSON Input to Python via Stdin
            pythonProcess.stdin.write(JSON.stringify(inputData));
            pythonProcess.stdin.end();

        } catch (err: any) {
            vscode.window.showErrorMessage(`Extension Error: ${err.message}`);
            this._panel.webview.postMessage({ type: 'error', message: err.message });
        }
    }

    public dispose() {
        PythonBridgePanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const x = this._disposables.pop();
            if (x) {
                x.dispose();
            }
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        const htmlPath = path.join(this._extensionPath, 'src', 'web', 'index.html');
        let htmlContent = fs.readFileSync(htmlPath, 'utf8');
        return htmlContent;
    }
}