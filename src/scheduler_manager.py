import subprocess
import logging
import re

class SchedulerManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    DAY_MAP = {
        "monday": "MON",
        "mon": "MON",
        "tuesday": "TUE",
        "tue": "TUE",
        "wednesday": "WED",
        "wed": "WED",
        "thursday": "THU",
        "thu": "THU",
        "friday": "FRI",
        "fri": "FRI",
        "saturday": "SAT",
        "sat": "SAT",
        "sunday": "SUN",
        "sun": "SUN",
    }

    def _run_schtasks(self, args):
        cmd = ["schtasks"] + args
        self.logger.info("Running scheduler command: %s", " ".join(cmd))
        return subprocess.run(cmd, capture_output=True, text=True, shell=False)

    def _normalize_time(self, time_text):
        if not isinstance(time_text, str):
            raise ValueError("Time must be in HH:MM format.")

        value = time_text.strip()
        match = re.match(r"^(\d{1,2}):(\d{2})$", value)
        if not match:
            raise ValueError("Time must be in HH:MM format.")

        hour = int(match.group(1))
        minute = int(match.group(2))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("Time must be between 00:00 and 23:59.")

        return f"{hour:02d}:{minute:02d}"

    def _normalize_day_of_week(self, day_text):
        if not isinstance(day_text, str) or not day_text.strip():
            raise ValueError("Weekly schedule requires a day of week.")

        token = day_text.strip().lower()
        normalized = self.DAY_MAP.get(token)
        if not normalized:
            raise ValueError("Invalid day of week.")
        return normalized

    def _normalize_day_of_month(self, day_value):
        try:
            day_int = int(day_value)
        except (TypeError, ValueError):
            raise ValueError("Monthly schedule requires a day of month between 1 and 31.")

        if day_int < 1 or day_int > 31:
            raise ValueError("Monthly schedule requires a day of month between 1 and 31.")
        return str(day_int)

    def _build_reminder_action(self, reminder_message):
        message = (reminder_message or "Time to run your backup job.").strip()
        if not message:
            message = "Time to run your backup job."

        # Escape quotes for cmd.exe
        escaped = message.replace('"', "'")
        return f'cmd.exe /c msg * "{escaped}"'

    def task_exists(self, task_name):
        result = self._run_schtasks(["/Query", "/TN", task_name])
        return result.returncode == 0

    def set_task_enabled(self, task_name, enabled):
        toggle = "/ENABLE" if enabled else "/DISABLE"
        result = self._run_schtasks(["/Change", "/TN", task_name, toggle])
        if result.returncode == 0:
            self.logger.info("Task '%s' %s.", task_name, "enabled" if enabled else "disabled")
            return True

        self.logger.warning(
            "Failed to change task '%s' to %s (code %s). stderr: %s",
            task_name,
            "enabled" if enabled else "disabled",
            result.returncode,
            (result.stderr or "").strip(),
        )
        return False

    def create_or_update_reminder(self, task_name, recurrence, run_time, reminder_message, day_of_week=None, day_of_month=None):
        recurrence_upper = (recurrence or "").strip().upper()
        if recurrence_upper not in ("WEEKLY", "MONTHLY"):
            raise ValueError("Recurrence must be WEEKLY or MONTHLY.")

        normalized_time = self._normalize_time(run_time)
        action = self._build_reminder_action(reminder_message)

        args = [
            "/Create",
            "/F",
            "/TN", task_name,
            "/TR", action,
            "/ST", normalized_time,
            "/SC", recurrence_upper,
        ]

        if recurrence_upper == "WEEKLY":
            args.extend(["/D", self._normalize_day_of_week(day_of_week)])
        else:
            args.extend(["/D", self._normalize_day_of_month(day_of_month)])

        result = self._run_schtasks(args)
        if result.returncode == 0:
            self.logger.info("Reminder task '%s' created/updated successfully.", task_name)
            return True

        self.logger.error(
            "Failed to create/update task '%s' (code %s). stderr: %s",
            task_name,
            result.returncode,
            (result.stderr or "").strip(),
        )
        return False

    def create_monthly_reminder(self, task_name="k_backups_reminder"):
        try:
            return self.create_or_update_reminder(
                task_name=task_name,
                recurrence="MONTHLY",
                run_time="09:00",
                reminder_message="Time to run your backup job.",
                day_of_month="1",
            )
        except Exception as e:
            self.logger.error("Error creating monthly reminder '%s': %s", task_name, e, exc_info=True)
            return False

    def remove_reminder(self, task_name="k_backups_reminder"):
        try:
            result = self._run_schtasks(["/Delete", "/F", "/TN", task_name])
            if result.returncode == 0:
                self.logger.info("Task deleted successfully.")
                return True
            else:
                self.logger.warning(
                    "Failed to delete task '%s' (return code %s). stderr: %s",
                    task_name,
                    result.returncode,
                    (result.stderr or "").strip(),
                )
                return False
        except Exception as e:
            self.logger.error(f"Error deleting task '{task_name}': {e}", exc_info=True)
            return False
