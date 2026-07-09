@echo off
echo ============================================
echo  Mempersiapkan Folder Automated Testing System
echo ============================================

echo [1] Membuat struktur folder utama...
mkdir "templates\components" 2>nul
mkdir "modules" 2>nul
mkdir "routes" 2>nul
mkdir "static\css" 2>nul
mkdir "static\js" 2>nul
mkdir "static\charts" 2>nul
mkdir "logs\testing" 2>nul
mkdir "static\testing" 2>nul
mkdir "static\testing\reports" 2>nul
mkdir "static\testing\exports" 2>nul
mkdir "data\testing" 2>nul
mkdir "backups\testing" 2>nul

echo [2] Membuat file template HTML...
echo. > "templates\testing_dashboard.html"
echo. > "templates\test_config.html"
echo. > "templates\test_results.html"
echo. > "templates\test_progress.html"
echo. > "templates\components\test_card.html"
echo. > "templates\components\test_charts.html"

echo [3] Membuat file Python modules...
echo. > "modules\testing_controller.py"
echo. > "modules\test_scenarios.py"
echo. > "modules\metrics_collector.py"
echo. > "modules\test_db.py"

echo [4] Membuat file routes...
echo. > "routes\testing_routes.py"

echo [5] Membuat file static...
echo. > "static\css\testing.css"
echo. > "static\js\testing.js"
echo. > "static\charts\testing_charts.js"

echo [6] Membuat file konfigurasi testing...
echo. > "testing_config.json"
echo. > "testing_requirements.txt"
echo. > "testing_readme.md"

echo [7] Membuat __init__.py untuk packages...
echo. > "modules\__init__.py"
echo. > "routes\__init__.py"
echo # Testing System Package > "modules\__init__.py"
echo # Testing Routes Package > "routes\__init__.py"

echo [8] Membuat database testing...
echo. > "testing_results.db"

echo.
echo ============================================
echo  SELESAI! Struktur folder berhasil dibuat.
echo ============================================
echo.
echo Struktur yang dibuat:
tree /F /A
pause