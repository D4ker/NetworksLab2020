@echo off
if not exist %1 (
	echo Error. File not found!
) else (
	set fpath=..
	echo Compile file %1...
	call pyinstaller --onefile %1
	move dist\*.exe
	rmdir /s /q %fpath%\__pycache__
	rmdir /s /q build
	rmdir /s /q dist
	del *.spec
)