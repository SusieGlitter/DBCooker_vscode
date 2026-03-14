import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as cp from 'child_process';

type Change = {
    originalLine?: string;
    newLine?: string;
    type: 'same' | 'added' | 'removed';
};

export const activeDiffStates = new Map<string, {
    uri: vscode.Uri;
    originalText: string;
    finalText: string;
    editor: vscode.TextEditor;
    backupPath: string;
    compilePath: string;
    deletionRanges: vscode.Range[];
    insertionRanges: vscode.Range[];
}>();

export const activeCommentThreads = new Map<string, vscode.CommentThread[]>();

export const insertionDecorationType = vscode.window.createTextEditorDecorationType({
    backgroundColor: 'rgba(32, 160, 32, 0.2)',
    isWholeLine: true,
    overviewRulerColor: 'green',
    overviewRulerLane: vscode.OverviewRulerLane.Full
});

export const deletionDecorationType = vscode.window.createTextEditorDecorationType({
    backgroundColor: 'rgba(255, 64, 64, 0.2)',
    isWholeLine: true,
    opacity: '0.6',
    overviewRulerColor: 'red',
    overviewRulerLane: vscode.OverviewRulerLane.Full
});

export async function confirmChanges(uriStr: string) {
    const state = activeDiffStates.get(uriStr);
    if (!state) return;
    const { editor, finalText, compilePath, backupPath } = state;

    const fullRange = new vscode.Range(
        editor.document.positionAt(0),
        editor.document.positionAt(editor.document.getText().length)
    );

    await editor.edit(editBuilder => {
        editBuilder.replace(fullRange, finalText);
    });

    editor.setDecorations(insertionDecorationType, []);
    editor.setDecorations(deletionDecorationType, []);
    await editor.document.save();

    // Sync to backup folder
    try {
        fs.copyFileSync(compilePath, backupPath);
    } catch(e) {
        console.error("Failed to sync backup", e);
    }
    
    vscode.window.setStatusBarMessage('Changes confirmed.', 3000);
    activeDiffStates.delete(uriStr);
    
    const threads = activeCommentThreads.get(uriStr);
    if (threads) {
        threads.forEach(t => t.dispose());
        activeCommentThreads.delete(uriStr);
    }
}

export async function discardChanges(uriStr: string) {
    const state = activeDiffStates.get(uriStr);
    if (!state) return;
    const { editor, originalText, compilePath, backupPath } = state;

    const fullRange = new vscode.Range(
        editor.document.positionAt(0),
        editor.document.positionAt(editor.document.getText().length)
    );

    await editor.edit(editBuilder => {
        editBuilder.replace(fullRange, originalText);
    });

    editor.setDecorations(insertionDecorationType, []);
    editor.setDecorations(deletionDecorationType, []);
    await editor.document.save();

    // Sync to compile folder
    try {
        fs.copyFileSync(backupPath, compilePath);
    } catch(e) {
        console.error("Failed to sync compile", e);
    }
    
    vscode.window.setStatusBarMessage('Changes discarded.', 3000);
    activeDiffStates.delete(uriStr);
    
    const threads = activeCommentThreads.get(uriStr);
    if (threads) {
        threads.forEach(t => t.dispose());
        activeCommentThreads.delete(uriStr);
    }
}

export async function showDiff(
    compilePath: string,
    backupPath: string,
    commentController: vscode.CommentController
) {
    console.log(`[Diff] showDiff called for: ${compilePath}`);
    const uri = vscode.Uri.file(compilePath);
    const uriStr = uri.toString();
    
    let editor = vscode.window.visibleTextEditors.find(e => e.document.uri.toString() === uriStr);
    if (!editor) {
        console.log(`[Diff] Opening new text document for ${compilePath}`);
        const document = await vscode.workspace.openTextDocument(uri);
        editor = await vscode.window.showTextDocument(document, { preview: false, preserveFocus: true });
    } else {
        console.log(`[Diff] Reusing existing editor for ${compilePath}`);
        // If it's already visible, we don't need to call showTextDocument again if we want to avoid focus switch
        // But we might want to ensure it's in the correct viewColumn if it's not active
        if (vscode.window.activeTextEditor !== editor) {
            await vscode.window.showTextDocument(editor.document, { 
                preview: false, 
                viewColumn: editor.viewColumn,
                preserveFocus: true
            });
        }
    }

    const document = editor.document;
    
    // Revert any unsaved changes (like previous diff views) to match the saved file on disk
    if (document.isDirty) {
        console.log(`[Diff] Reverting unsaved changes in ${compilePath} before diff`);
        await vscode.commands.executeCommand('workbench.action.files.revert');
    }

    const newContent = fs.readFileSync(compilePath, 'utf8');
    const originalText = fs.readFileSync(backupPath, 'utf8');
    
    console.log(`[Diff] Computing line diff for ${compilePath}`);
    // 1. Calculate Diff (Line by Line)
    const changes = computeLineDiff(originalText, newContent);

    // 2. Construct "Hybrid" Text and decoration ranges
    let hybridText = "";
    const deletionRanges: vscode.Range[] = [];
    const insertionRanges: vscode.Range[] = [];

    let currentLine = 0;
    let inHunk = false;
    const hunks: { startLine: number }[] = [];

    for (const change of changes) {
        if (change.type === 'removed') {
            if (!inHunk) {
                inHunk = true;
                hunks.push({ startLine: currentLine });
            }
            const lineContent = "- " + change.originalLine + "\n";
            hybridText += lineContent;
            
            const start = new vscode.Position(currentLine, 0);
            const end = new vscode.Position(currentLine, 0); 
            deletionRanges.push(new vscode.Range(start, end));
            currentLine++;
        } 
        else if (change.type === 'added') {
            if (!inHunk) {
                inHunk = true;
                hunks.push({ startLine: currentLine });
            }
            const lineContent = "+ " + change.newLine + "\n";
            hybridText += lineContent;
            
            const start = new vscode.Position(currentLine, 0);
            const end = new vscode.Position(currentLine, 0);
            insertionRanges.push(new vscode.Range(start, end));
            currentLine++;
        } 
        else {
            inHunk = false;
            // Same
            hybridText += "  " + change.originalLine + "\n";
            currentLine++;
        }
    }
    
    // Clean trailing newline logic
    if (!originalText.endsWith('\n') && hybridText.endsWith('\n')) {
         hybridText = hybridText.slice(0, -1);
    }

    console.log(`[Diff] Applying hybrid text to editor for ${compilePath}`);
    // 3. Replace Editor Content with Hybrid View
    const fullRange = new vscode.Range(
        document.positionAt(0),
        document.positionAt(newContent.length)
    );

    await editor.edit(editBuilder => {
        editBuilder.replace(fullRange, hybridText);
    });

    console.log(`[Diff] Setting decorations for ${compilePath}`);
    // 4. Apply Decorations
    editor.setDecorations(deletionDecorationType, deletionRanges);
    editor.setDecorations(insertionDecorationType, insertionRanges);

    // 5. Update State
    activeDiffStates.set(uriStr, {
        uri,
        editor,
        originalText,
        finalText: newContent,
        compilePath,
        backupPath,
        deletionRanges,
        insertionRanges
    });

    console.log(`[Diff] Creating comment threads for ${compilePath}`);
    // 6. Create Comment Thread for "Big Buttons"
    const existingThreads = activeCommentThreads.get(uriStr);
    if (existingThreads) {
        existingThreads.forEach(t => t.dispose());
    }
    
    const newThreads: vscode.CommentThread[] = [];
    for (const hunk of hunks) {
        const range = new vscode.Range(hunk.startLine, 0, hunk.startLine, 0);
        const thread = commentController.createCommentThread(uri, range, []);
        thread.canReply = false;
        
        const markdown = new vscode.MarkdownString(
            `[✅ 接受全部更改 (Accept All)](command:cppHelper.confirm?${encodeURIComponent(JSON.stringify([uriStr]))}) &nbsp;&nbsp;&nbsp; [❌ 放弃全部更改 (Discard All)](command:cppHelper.discard?${encodeURIComponent(JSON.stringify([uriStr]))})`
        );
        markdown.isTrusted = true;

        thread.comments = [{
            author: { name: 'Diff' },
            body: markdown,
            mode: vscode.CommentMode.Preview
        }];
        newThreads.push(thread);
    }

    activeCommentThreads.set(uriStr, newThreads);

    // Scroll to first change
    if (insertionRanges.length > 0) editor.revealRange(insertionRanges[0]);
    else if (deletionRanges.length > 0) editor.revealRange(deletionRanges[0]);
    console.log(`[Diff] showDiff completed for ${compilePath}`);
}

export function reapplyDecorations(editor: vscode.TextEditor) {
    const uriStr = editor.document.uri.toString();
    const state = activeDiffStates.get(uriStr);
    if (state) {
        editor.setDecorations(deletionDecorationType, state.deletionRanges);
        editor.setDecorations(insertionDecorationType, state.insertionRanges);
    }
}

export function computeLineDiff(original: string, modified: string): Change[] {
    const lines1 = original.split(/\r?\n/);
    const lines2 = modified.split(/\r?\n/);

    const matrix: number[][] = [];
    for (let i = 0; i <= lines1.length; i++) {
        matrix[i] = new Array(lines2.length + 1).fill(0);
    }

    for (let i = 1; i <= lines1.length; i++) {
        for (let j = 1; j <= lines2.length; j++) {
            if (lines1[i - 1] === lines2[j - 1]) {
                matrix[i][j] = matrix[i - 1][j - 1] + 1;
            } else {
                matrix[i][j] = Math.max(matrix[i - 1][j], matrix[i][j - 1]);
            }
        }
    }

    const changes: Change[] = [];
    let i = lines1.length;
    let j = lines2.length;

    while (i > 0 || j > 0) {
        if (i > 0 && j > 0 && lines1[i - 1] === lines2[j - 1]) {
            changes.unshift({ originalLine: lines1[i - 1], type: 'same' });
            i--;
            j--;
        } else if (j > 0 && (i === 0 || matrix[i][j - 1] >= matrix[i - 1][j])) {
            changes.unshift({ newLine: lines2[j - 1], type: 'added' });
            j--;
        } else if (i > 0 && (j === 0 || matrix[i][j - 1] < matrix[i - 1][j])) {
            changes.unshift({ originalLine: lines1[i - 1], type: 'removed' });
            i--;
        }
    }

    return changes;
}
