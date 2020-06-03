import datetime
import tkinter as tk
from tkinter import ttk, messagebox, font
from sqlalchemy import create_engine, Table, Column, Integer, String, DateTime, Date
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class History(Base):
    __tablename__ = 'history_records'
    id = Column('id', Integer, primary_key=True, autoincrement=True)
    created_at = Column('created_at', DateTime(), default=datetime.datetime.utcnow)
    query = Column('query', String(), nullable=False)
    start_date = Column('start_date', Date())
    end_date = Column('end_date', Date())


class Info(Base):
    __tablename__ = 'info'
    id = Column('id', Integer, primary_key=True, autoincrement=True)
    scopus_key = Column('scopus_key', String(), nullable=False)


class MyApp(object):
    def __init__(self):
        root = tk.Tk()
        root.title('MUMT-MIS: SCOPUS Pub Downloader')
        #root.tk.call('tk', 'scaling', 1.25)
        root.protocol('WM_DELETE_WINDOW', root.destroy)
        self.default_font = font.nametofont("TkDefaultFont")
        #default_font_size = self.default_font['size']

        win = ttk.Frame(root)
        win.grid(column=0, row=0, sticky=(tk.W, tk.E, tk.S, tk.N))
        ttk.Label(win, text='This is my font.', font=self.default_font).grid(column=0, row=0)
        ttk.Button(win, text='Hit me', command=lambda: self.alert('Button info', 'I was tapped.')).grid()
        root.attributes('-topmost', True)
        root.mainloop()

    def alert(self, title, msg, type_='info'):
        if type_ == 'info':
            messagebox.showinfo(title, msg)
        elif type_ == 'error':
            messagebox.showerror(title, msg)


def main():
    engine = create_engine('sqlite:///db.sqlite')
    root = tk.Tk()
    root.withdraw()
    try:
        connect = engine.connect()
    except:
        Base.metadata.create_all(engine)
        messagebox.showinfo('Information', 'New database file has been created.')
        root.destroy()
    else:
        messagebox.showinfo('Information', 'Database file exists.')
        root.destroy()
        app = MyApp()


if __name__ == '__main__':
    main()
