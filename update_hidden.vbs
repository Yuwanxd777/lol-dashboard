' 排程用：隱藏視窗執行 publish.bat（更新資料＋自動推上 GitHub Pages），不跳黑窗、不搶鍵盤焦點
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
sh.Run """" & here & "\publish.bat""", 0, True
