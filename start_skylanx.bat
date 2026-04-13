@echo off

cd "frontend"
START runner.bat
cd..

cd "backend"
START runner.bat
cd..

explorer "http://localhost:8080"

exit