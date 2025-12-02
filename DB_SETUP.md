DB setup — minimal (SQL-only)

This repository includes a schema-only SQL file `dsp_final_schema.sql` that creates an empty `dsp_final` database and the `patients` table required by the project.

To create a local live database (assumes you have MySQL installed locally):

1. From the repo root, run:

```powershell
# One-command (PowerShell): prompt for password and import
# from repo root
.\setup-db.ps1 -PromptForPassword
```

If you prefer to use the `mysql` client directly (PowerShell treats `<` as a redirection token), use one of these options:

```powershell
# run redirection inside cmd.exe (works the same as bash/cmd)
cmd /c "mysql -u root -p < dsp_final_schema.sql"

# or pipe file contents to mysql (PowerShell native)
Get-Content .\dsp_final_schema.sql -Raw | mysql -u root -p
```

PowerShell execution policy note
--------------------------------

Windows PowerShell may block running scripts by default (you'll see an error like "running scripts is disabled on this system"). Recommended, temporary ways to run `setup-db.ps1` safely:

- Temporarily allow scripts only for the current PowerShell process (no admin required):

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
.\setup-db.ps1 -PromptForPassword
```

- Run the script in a new PowerShell process with an execution-policy override (one-shot):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-db.ps1 -PromptForPassword
```

- If you don't want to change execution policy at all, you can pipe the schema directly (no script):

```powershell
Get-Content .\dsp_final_schema.sql -Raw | mysql -u root -p
```

- If Windows blocked the file as downloaded, you can unblock it first:

```powershell
Unblock-File .\setup-db.ps1
```

The first option (`-Scope Process`) is recommended because it's temporary and does not alter system-wide settings.

2. If you need to specify host/port/user, run:

```powershell
mysql -u myuser -p -h 127.0.0.1 -P 3306 dsp_final < dsp_final_schema.sql
```

That's it — the `dsp_final` database with an empty `patients` table will be available locally for your app to connect to.

Optional: create a `.env` file with connection settings for your app (example):

```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=yourpassword
DB_NAME=dsp_final
```

If you later want a helper script or a small seeded dump for testing, I can add that on request.
