@echo off
setlocal

set SOURCE=C:\QOS
set DESTINATION=%UserProfile%\OneDrive\QOS_BACKUP

robocopy "%SOURCE%" "%DESTINATION%" /MIR /NFL /NDL /NP /NJH /NJS

echo Cloud sync complete.
# Updated at 2025-06-15 10:38:17.494266
# Updated at 2025-06-15 20:39:43.791009