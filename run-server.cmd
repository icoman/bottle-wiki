@echo off

SET DSN=sqlite:///wiki.db
SET PORT=80
SET HOST=localhost

:loop
python web-server.py
pause
goto loop

