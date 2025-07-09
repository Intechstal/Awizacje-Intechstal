import sqlite3

def init_db():
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS awizacje (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firma TEXT NOT NULL,
            rejestracja TEXT NOT NULL,
            kierowca TEXT NOT NULL,
            data_godzina TEXT NOT NULL,
            typ_ladunku TEXT NOT NULL,
            komentarz TEXT,
            status TEXT DEFAULT 'oczekująca'
        )
    ''')
    conn.commit()
    conn.close()

def dodaj_awizacje(firma, rejestracja, kierowca, data_godzina, typ_ladunku, komentarz):
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO awizacje (firma, rejestracja, kierowca, data_godzina, typ_ladunku, komentarz)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (firma, rejestracja, kierowca, data_godzina, typ_ladunku, komentarz))
    conn.commit()
    conn.close()

def pobierz_awizacje():
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('SELECT * FROM awizacje')
    wyniki = c.fetchall()
    conn.close()
    return wyniki
