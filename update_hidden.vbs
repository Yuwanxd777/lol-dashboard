' 排程用：隱藏視窗執行 publish.bat（更新資料＋自動推上 GitHub Pages），不跳黑窗、不搶鍵盤焦點
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
rc = sh.Run("""" & here & "\publish.bat""", 0, True)
' 把 publish.bat 的離開碼（#46：守門結論）帶給工作排程器，否則「上次結果」永遠是 0
WScript.Quit rc
