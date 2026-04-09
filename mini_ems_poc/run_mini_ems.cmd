@echo off
cd /d C:\dev\openems\mini_ems_poc

if not exist logs mkdir logs

"C:\Users\ENGIE_NL_STUTTGART\AppData\Local\Programs\Python\Python312\python.exe" ^
  "C:\dev\openems\mini_ems_poc\mini_ems.py" ^
  --config "C:\dev\openems\mini_ems_poc\config.json" ^
  --loop >> "C:\dev\openems\mini_ems_poc\logs\mini_ems_stdout.log" 2>&1
