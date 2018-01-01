from app import create_app

app = create_app()

@app.cli.command()
def initdb():
    """Initialize the database"""
    print('Initializing the database...')


if __name__ == '__main__':
    app.run(debug=True, port=5555)