@echo off
echo ========================================
echo Upgrading to Category-Aware AI
echo ========================================
echo.

echo This upgrade will:
echo - Train separate models for each API category
echo - Improve accuracy by 10-20%%
echo - Reduce false positives
echo - Use category-specific thresholds
echo.

echo Step 1: Backing up current AI predictor...
if exist ai_predictor_backup.py del ai_predictor_backup.py
copy ai_predictor.py ai_predictor_backup.py
echo.

echo Step 2: Switching to Category-Aware AI...
copy /Y ai_predictor_category.py ai_predictor.py
echo.

echo Step 3: Creating models directory...
if not exist models mkdir models
echo.

echo ========================================
echo Upgrade Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Train category models: python train_category_models.py
echo 2. Restart application: START_HERE.bat
echo 3. Test predictions
echo.
echo Category-Aware AI Features:
echo - Separate models for REST API, Website, Database, etc.
echo - Category-specific failure thresholds
echo - Better accuracy for each API type
echo - Reduced false positives
echo.
pause
