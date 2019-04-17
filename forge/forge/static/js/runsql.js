function onReady() {
    addDefaultActionButtonListener();
    $("#stackInformation").hide();
    var stacks = document.getElementsByClassName("selectStackOption");

    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            $("#log").css("background", "rgba(0,20,70,.08)");
            selectStack(data.target.text);
            send_http_get_request(baseUrl + "/getsql/" + region + "/" + data.target.text, displaySQL);
        });
    }
}

function displaySQL(responseText) {
    $("#log").css("background", "rgba(0,0,0,0)");

    $("#log").contents().find('body').html(responseText
        .substr(1, responseText.length - 3)
        .split('\\n').join('<br />'));
}