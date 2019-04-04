import forge

app = forge.create_app('forge.config.BaseConfig')

if __name__ == '__main__':
    app.run(threaded=True, host='0.0.0.0', port=8000)
