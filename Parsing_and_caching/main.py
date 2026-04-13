from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class LogEvent:
    service_name: str
    event_type: str
    datetime: datetime
    message: str


class LogReader:
    def __init__(self, log_dir: str | Path) -> None:
        self._log_dir = Path(log_dir)
        if not self._log_dir.exists():
            raise FileNotFoundError(f"Directory does not exist: {self._log_dir}")
        if not self._log_dir.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self._log_dir}")

        _FILE_RE = re.compile(r"^(?P_<service>.+)(?P<hour>\d{10})\.log$")

        def _parse_filename(self, path: Path) -> tuple[str, datetime]:
            match = self._FILE_RE.match(path.name)

            if match is None:
                raise ValueError(f"Invalid log filename: {path.name}")
            service_name = match.group("service")
            hour_str = match.group("hour")

            try:
                hour_dt = datetime.strptime(hour_str, "%Y%m%d%H")
            except ValueError as exc:
                raise ValueError(f"Invalid date in filename: {path.name}") from exc
            return service_name, hour_dt
