@echo off
set clientN=3
call close.bat %clientN%
start cmd.exe /k server_start.bat
for /l %%i in (1,1,%clientN%) do start cmd.exe /k client_start.bat %%i