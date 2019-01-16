function onReady() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            $("#cancelZDUButton").removeAttr("disabled");
            selectStack(data.target.text);
        }, false);
    }
    $("#action-button").on("click", beginUpgrade);
}

function beginUpgrade() {
    if (document.getElementById("zduCheckBox").checked) {
        $("#auth-ok-btn").on("click", performUpgrade);
        AJS.dialog2("#auth-dialog").show();
    }
    else {
        performUpgrade();
    }
}

function performUpgrade() {
    var zdu = document.getElementById("zduCheckBox").checked;
    var version = $("#upgradeVersionSelector").val();
    var stack_name = scrapePageForStackName();
    var url = baseUrl + "/do" + action + "/" + region + "/" + stack_name;

    var upgradeRequest = new XMLHttpRequest();
    url += "/" + version + "/" + zdu;

    upgradeRequest.open("POST", url, true);
    upgradeRequest.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
    upgradeRequest.addEventListener("load", processResponse);
    upgradeRequest.send(JSON.stringify(zdu ? getAuthDetailsAsJSON() : [{}]));

    redirectToLog(stack_name);
}