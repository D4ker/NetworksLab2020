@echo off
for /f "tokens=2 USEBACKQ" %%f IN (`tasklist /NH /FI "WINDOWTITLE eq test_server2020"`) do set ourPID=%%f
set /a _ourPID=ourPID*1
if "%ourPID%" == "%_ourPID%" call taskkill /F /T /PID %ourPID%

set i=%1
:pid_find
for /f "tokens=2 USEBACKQ" %%f IN (`tasklist /NH /FI "WINDOWTITLE eq test_client2020"`) do set ourPID=%%f
set /a i-=1
set /a _ourPID=ourPID*1
if "%ourPID%" == "%_ourPID%" call taskkill /F /T /PID %ourPID%
if /i %i% geq 0 goto pid_find
:end