import forge

app = forge.create_app()

if __name__ == '__main__':
    app.run(threaded=True, debug=False, host='0.0.0.0', port=8000)