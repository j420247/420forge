function beginUpgrade() {
    if (document.getElementById("zduCheckBox").checked) {
        AJS.dialog2("#auth-dialog").show();
    }
    else {
        performUpgrade();
    }
}

function performUpgrade() {
    var zdu = document.getElementById("zduCheckBox").checked;
    var username = $('#username').val();
    var password = $('#password').val();
    var version = $("#upgradeVersionSelector").val();
    var stack_name = scrapePageForStackName();
    var url = baseUrl + "/do" + action + "/" + region + "/" + stack_name;

    var upgradeRequest = new XMLHttpRequest();
    url += "/" + version + "/" + zdu;

    upgradeRequest.open("POST", url, true);
    upgradeRequest.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
    upgradeRequest.addEventListener("load", processResponse);

    // send the collected data as JSON
    var jsonArray = [];
    var authDetails = {};
    if (zdu) {
        authDetails["username"] = username;
        authDetails["password"] = password;
    }
    jsonArray.push(authDetails);
    upgradeRequest.send(JSON.stringify(jsonArray));

    // Wait a mo for action to begin  in backend
    setTimeout(function () {
        // Redirect to action progress screen
        window.location = baseUrl + "/actionprogress/" + action + "?stack=" + stack_name;
    }, 1000);
}