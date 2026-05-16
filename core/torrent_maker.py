from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import libtorrent as lt

from core.trackers import PUBLIC_TRACKERS


@dataclass(frozen=True)
class CreatedTorrent:
    name: str
    output_path: str
    file_count: int
    total_size: int
    piece_size: int


def make_torrent_from_folder(
    folder_path: str,
    output_path: Optional[str] = None,
    trackers: Optional[Iterable[str]] = None,
    comment: Optional[str] = None,
    private: bool = False,
) -> CreatedTorrent:
    """Create a v1 .torrent file from a local folder."""
    source = Path(folder_path).expanduser().resolve()
    if not source.exists():
        raise ValueError("Folder does not exist")
    if not source.is_dir():
        raise ValueError("Path is not a folder")

    destination = _resolve_output_path(source, output_path)
    if _is_relative_to(destination, source):
        raise ValueError("Output .torrent cannot be inside the source folder")

    fs = lt.file_storage()
    lt.add_files(fs, str(source))
    if fs.num_files() == 0:
        raise ValueError("Folder has no files")

    destination.parent.mkdir(parents=True, exist_ok=True)

    torrent = lt.create_torrent(fs, 0, lt.create_torrent.v1_only)
    torrent.set_creator("FSMagnet")
    torrent.set_comment(comment or "Created by FSMagnet")
    torrent.set_priv(bool(private))

    tracker_list = list(trackers) if trackers is not None else PUBLIC_TRACKERS
    for tier, tracker in enumerate(t for t in tracker_list if t):
        torrent.add_tracker(str(tracker), tier)

    lt.set_piece_hashes(torrent, str(source.parent))
    destination.write_bytes(bytes(lt.bencode(torrent.generate())))

    return CreatedTorrent(
        name=fs.name(),
        output_path=str(destination),
        file_count=fs.num_files(),
        total_size=fs.total_size(),
        piece_size=torrent.piece_length(),
    )


def _resolve_output_path(source: Path, output_path: Optional[str]) -> Path:
    if not output_path:
        return source.parent / f"{source.name}.torrent"

    destination = Path(output_path).expanduser()
    if destination.exists() and destination.is_dir():
        return (destination / f"{source.name}.torrent").resolve()
    if destination.suffix.lower() != ".torrent":
        return (destination / f"{source.name}.torrent").resolve()
    return destination.resolve()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
