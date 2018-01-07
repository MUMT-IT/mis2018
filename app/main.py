from app import create_app
from app.database import create_db, load_orgs

app = create_app()

@app.cli.command()
def initdb():
    """Initialize the database"""
    create_db()


@app.cli.command()
def populatedb():
    load_orgs()


if __name__ == '__main__':
    app.run(debug=True, port=5555)