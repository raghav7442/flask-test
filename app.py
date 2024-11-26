from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=['GET'])
def check():
    print("Hello vkaps")
    return "Everything Is Running??"



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
