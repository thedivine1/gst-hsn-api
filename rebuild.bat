@echo off
set PYTHONIOENCODING=utf-8
call venv\Scripts\python build_gst_master.py
call venv\Scripts\python populate_sac_rates.py
call venv\Scripts\python fix_missing_schedules.py
call venv\Scripts\python dedup_hsn.py
call venv\Scripts\python one_off_fix.py
call venv\Scripts\python load_data.py
