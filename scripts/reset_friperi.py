"""Explicit, twice-confirmed factory reset. Stop FriPeri before running this script."""
from pathlib import Path
import os
import re
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]


def checked(root, target):
    if target.is_symlink() or not target.resolve().is_relative_to(root):
        raise OSError(f'Refusing unsafe runtime path: {target}')
    return target


def reset_plan(root):
    root = root.resolve()
    database = checked(root, root / 'db')
    uploads = checked(root, root / 'static' / 'uploads')
    targets = []
    if database.exists():
        for item in database.iterdir():
            if re.fullmatch(r'.+\.(?:db|sqlite|sqlite3)(?:-wal|-shm|-journal|\.pre-language-v1\.bak)?', item.name) or item.name == '.setup.lock':
                targets.append(checked(root, item))
    if uploads.exists():
        def collect(directory):
            for item in directory.iterdir():
                checked(root, item)
                if item.is_dir():
                    collect(item)
                    targets.append(item)
                elif item.name != '.gitkeep':
                    targets.append(item)
        collect(uploads)
    for name in ('.env', '.env.bak'):
        target = checked(root, root / name)
        if target.exists():
            targets.append(target)
    # Reject overrides we cannot safely reset rather than report a false factory state.
    from dotenv import dotenv_values
    config = {**dotenv_values(root / '.env'), **os.environ}
    for key, directory in (('SITE_DB_PATH', database), ('SITE_UPLOAD_DIR', uploads)):
        if config.get(key):
            target = Path(config[key])
            if not target.is_absolute():
                target = root / target
            checked(root, target)
            if (key == 'SITE_UPLOAD_DIR' and target.resolve() != directory.resolve()) or (key == 'SITE_DB_PATH' and (target.parent.resolve() != database.resolve() or not re.fullmatch(r'.+\.(db|sqlite|sqlite3)', target.name))):
                raise OSError(f'{key} points outside the standard reset scope; reset cannot safely proceed.')
    return targets


def main(root=None, input_fn=input, output=print):
    root = (root or ROOT_DIR).resolve()
    output('--------------------------------------------------\nWARNING: FriPeri FACTORY RESET\n--------------------------------------------------')
    output('Stop FriPeri before continuing. This action cannot be undone.')
    output('This permanently deletes all content, categories, menu configuration, design/contact/social settings, custom translations, users/admin credentials, database backups, uploaded files, and generated .env/.env.bak configuration.')
    try:
        if input_fn('Continue? [y/N] ').lower() not in ('y', 'yes'):
            output('Reset cancelled. No changes were made.')
            return 0
        targets = reset_plan(root)
        output('Data to remove: databases and migration backups in db/; user files in static/uploads/; generated .env and .env.bak. All DB content, settings, translations and credentials are included.')
        output('Application source, templates, CSS/JS, built-in translations and uploads/.gitkeep will be preserved.')
        if input_fn('Type "RESET FriPeri" to permanently erase all FriPeri data: ') != 'RESET FriPeri':
            output('Reset cancelled. No changes were made.')
            return 0
        for target in targets:
            checked(root, target)
            if target.is_dir():
                target.rmdir()
            else:
                target.unlink(missing_ok=True)
        output('✓ Database removed\n✓ Uploaded files removed\n✓ Runtime configuration cleared')
        output('FriPeri has been reset successfully.\n\nStart FriPeri normally:\nuvicorn main:app --host 127.0.0.1\n\nThen open the site to begin first-run setup.')
        return 0
    except (EOFError, KeyboardInterrupt):
        output('Reset cancelled. No changes were made.')
        return 0
    except OSError as exc:
        output(f'Reset failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
