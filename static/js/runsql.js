function onReady() {
    addDefaultActionButtonListener();
    $("#stackInformation").hide();
    var stacks = document.getElementsByClassName("selectStackOption");

    for (var i = 0; i < stacks.length; i ++) {
        stacks[i].addEventListener("click", function (data) {
            $("#log").css("background", "rgba(0,20,70,.08)");
            selectStack(data.target.text);

            var getSqlRequest = new XMLHttpRequest();
            getSqlRequest.open("GET", baseUrl + "/getsql/" + region + "/" + data.target.text, true);
            getSqlRequest.setRequestHeader("Content-Type", "text/xml");
            getSqlRequest.onreadystatechange = function () {
                if (getSqlRequest.readyState === XMLHttpRequest.DONE && getSqlRequest.status === 200) {
                    $("#log").css("background", "rgba(0,0,0,0)");

                    $("#log").contents().find('body').html(getSqlRequest.responseText
                        .substr(1, getSqlRequest.responseText.length - 3)
                        .split('\\n').join('<br />'));
                }
            };
            getSqlRequest.send();
        }, false);
    }
}

