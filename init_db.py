"""Create the database and add starter movies. SAFE to run repeatedly:
it never deletes existing data. Use `python init_db.py --reset` to wipe it
(you will be asked to confirm)."""
import sqlite3
import sys

from app import DB_PATH, init_schema

# Only public-domain / Creative Commons / your own material belongs here.
# Poster + video are filenames inside static/media/ or full https:// URLs.
STARTER_MOVIES = [
    ("GBU Dandiya", "2026", "Gautam buddha university", "my_film.jpeg", "my_film.mp4"),
    ("Dominate", "2024", "A short original film.", "dominate.jpg", "my_movie.mp4"),
    ("Future Earth", "2050", "A look at a predicted future Earth.", "earth.jpg", "earth.mp4"),
    ("Link Without Hook", "2020", "Original music video.", "link_without_hook.jpg", "song.mp4"),
    ("Big Buck Bunny", "2008",
     "A giant rabbit gets revenge. (c) Blender Foundation, CC BY 3.0.",
     "bunny.jpg",
     "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"),
]


def main():
    reset = '--reset' in sys.argv
    if reset and input('This DELETES every movie. Type YES to continue: ') != 'YES':
        print('Cancelled.')
        return
    with sqlite3.connect(DB_PATH) as conn:
        if reset:
            conn.execute('DROP TABLE IF EXISTS movies')
    init_schema()
    with sqlite3.connect(DB_PATH) as conn:
        count = conn.execute('SELECT COUNT(*) FROM movies').fetchone()[0]
        if count == 0:
            conn.executemany(
                'INSERT INTO movies (title, year, description, poster, video) VALUES (?, ?, ?, ?, ?)',
                STARTER_MOVIES)
            print(f'Database ready at {DB_PATH}: added {len(STARTER_MOVIES)} starter movies.')
        else:
            print(f'Database ready at {DB_PATH}: kept your {count} existing movies (nothing changed).')


if __name__ == '__main__':
    main()
