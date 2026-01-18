import os
import queue
import shutil
from datetime import datetime
from typing import Optional

from organiser.exif_utils import get_exif_datetime_original, IMAGE_EXTS
from organiser.duplicate_finder import DuplicateFinder


def get_file_timestamp(
    path: str, date_source: str, log_q: Optional[queue.Queue] = None
) -> float:
    if date_source == "Auto":
        ext = os.path.splitext(path)[1].lower()
        if ext in IMAGE_EXTS:
            exif_dt = get_exif_datetime_original(path)
            if exif_dt is not None:
                return exif_dt.timestamp()
            date_source = "Modified"
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        mtime = None
    try:
        ctime = os.path.getctime(path)
    except Exception:
        ctime = None
    if date_source == "Modified":
        if mtime is not None:
            return mtime
        if ctime is not None:
            if log_q:
                log_q.put(
                    f"Warning: Modified time unavailable for {path}, using created time"
                )
            return ctime
        raise RuntimeError(f"No timestamp available for {path}")
    if date_source == "Created":
        if ctime is not None:
            return ctime
        if mtime is not None:
            if log_q:
                log_q.put(
                    f"Warning: Created time unavailable for {path}, using modified time"
                )
            return mtime
        raise RuntimeError(f"No timestamp available for {path}")
    if date_source == "Earliest":
        candidates = [t for t in (mtime, ctime) if t is not None]
        if candidates:
            return min(candidates)
        raise RuntimeError(f"No timestamp available for {path}")
    if date_source == "Latest":
        candidates = [t for t in (mtime, ctime) if t is not None]
        if candidates:
            return max(candidates)
        raise RuntimeError(f"No timestamp available for {path}")
    if date_source == "EXIF (images)":
        exif_dt = get_exif_datetime_original(path)
        if exif_dt is not None:
            return exif_dt.timestamp()
        if mtime is not None:
            if log_q:
                log_q.put(f"Notice: EXIF not found for {path}, using modified time")
            return mtime
        if ctime is not None:
            if log_q:
                log_q.put(
                    f"Notice: EXIF and modified time not found for {path}, using created time"
                )
            return ctime
        raise RuntimeError(f"No timestamp available for {path}")
    if mtime is not None:
        return mtime
    if ctime is not None:
        return ctime
    raise RuntimeError(f"No timestamp available for {path}")


def organise_files_worker(
    source_dir, dest_dir, date_source, log_q, status_q, progress_q, stop_event, log_path
):
    files = [
        os.path.join(dp, f)
        for dp, dn, filenames in os.walk(source_dir)
        for f in filenames
        if not f.startswith(".")
    ]
    total = len(files)
    duplicate_finder = DuplicateFinder()
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log_file = open(log_path, "a", encoding="utf-8")
    except Exception:
        log_file = open(os.path.basename(log_path), "a", encoding="utf-8")
    log_file.write(f"Start: {datetime.now().isoformat()}\n")
    log_file.write(f"Date source: {date_source}\n")
    log_file.flush()
    try:
        if total == 0:
            status_q.put("No files found")
            log_q.put("No files found")
            progress_q.put((0, 1))
            return
        for count, file in enumerate(files, 1):
            if stop_event.is_set():
                status_q.put("Cancelled by user")
                log_q.put("Cancelled by user")
                log_file.write(
                    f"Cancelled at {datetime.now().isoformat()} after {count - 1} files\n"
                )
                break
            try:
                ext = os.path.splitext(file)[1].lower()
                is_image = ext in IMAGE_EXTS
                is_duplicate = False
                if is_image:
                    is_duplicate = duplicate_finder.check_and_record(file)
                if is_duplicate:
                    # Move to duplicates folder under dest_dir
                    ts = get_file_timestamp(file, date_source, log_q)
                    modified = datetime.fromtimestamp(ts)
                    year = modified.strftime("%Y")
                    month = modified.strftime("%m")
                    dup_dir = os.path.join(dest_dir, "duplicates", year, month)
                    os.makedirs(dup_dir, exist_ok=True)
                    dest_path = os.path.join(dup_dir, os.path.basename(file))
                    shutil.move(file, dest_path)
                    msg = f"Duplicate: {file} -> {dest_path}"
                    status_q.put(f"Duplicate: {count}/{total}")
                    log_q.put(msg)
                    log_file.write(msg + "\n")
                else:
                    ts = get_file_timestamp(file, date_source, log_q)
                    modified = datetime.fromtimestamp(ts)
                    year = modified.strftime("%Y")
                    month = modified.strftime("%m")
                    target_dir = os.path.join(dest_dir, year, month)
                    os.makedirs(target_dir, exist_ok=True)
                    dest_path = os.path.join(target_dir, os.path.basename(file))
                    shutil.move(file, dest_path)
                    msg = f"Moved: {file} -> {dest_path}"
                    status_q.put(f"Moving: {count}/{total}")
                    log_q.put(msg)
                    log_file.write(msg + "\n")
            except Exception as e:
                err = f"Error: {file} ({e})"
                status_q.put(err)
                log_q.put(err)
                log_file.write(err + "\n")
            progress_q.put((count, total))
        else:
            num_dups = len(duplicate_finder.get_duplicates())
            status_q.put(
                f"✅ Done organizing {total} files. {num_dups} duplicates moved."
            )
            log_q.put(f"✅ Done organizing {total} files. {num_dups} duplicates moved.")
            log_file.write(
                f"Completed: {datetime.now().isoformat()} - {total} files, {num_dups} duplicates moved\n"
            )
    finally:
        try:
            log_file.flush()
            log_file.close()
        except Exception:
            pass
        status_q.put("__WORKER_FINISHED__")
