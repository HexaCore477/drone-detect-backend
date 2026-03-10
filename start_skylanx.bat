@echo off

cd "frontend"
START runner.bat
cd..

cd "backend"
START runner.bat
cd..

exit