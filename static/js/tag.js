var stack_name;

$(document).ready(function() {
    $("#stackInformation").hide();
    $("#tags").hide();
    var stacks = document.getElementsByClassName("selectStackOption");

    for (var i = 0; i < stacks.length; i ++) {
        stacks[i].addEventListener("click", function (data) {
            $("#stackInformation").show();
            $("#tags").show();
            stack_name = data.target.text;
            selectStack(stack_name);
            getTags(stack_name);
        }, false);
    }

    var actionButton = document.getElementById("action-button");
    actionButton.removeEventListener("click", defaultActionBtnEvent);
    actionButton.addEventListener("click", function (data) {
        sendTagsAsJson();
    });
});

function getTags() {
    var getTagsRequest = new XMLHttpRequest();
    getTagsRequest.open("GET", baseUrl + "/getTags/" + env + "/" + stack_name, true); //TODO update to region when region PR merged
    getTagsRequest.setRequestHeader("Content-Type", "text/xml");
    getTagsRequest.onreadystatechange = function () {
        if (getTagsRequest.readyState === XMLHttpRequest.DONE && getTagsRequest.status === 200) {
            tags = JSON.parse(getTagsRequest.responseText);
            $("#existing-tags").hide;
            var tagsList = document.getElementById("existing-tags");

            for (var tag in tags) {
                var div = document.createElement("DIV");
                div.className = "field-group";

                var keyInput = document.createElement("INPUT");
                keyInput.className = "text";
                keyInput.type = "text";
                keyInput.name = "key";
                keyInput.value = tags[tag].Key;

                var valInput = document.createElement("INPUT");
                valInput.className = "text";
                valInput.type = "text";
                valInput.name = "value";
                valInput.value = tags[tag].Value;

                var delBtn = document.createElement("SPAN");
                delBtn.innerHTML = "<span class=\"aui-icon aui-icon-small aui-iconfont-delete\">Delete</span>";

                div.appendChild(keyInput);
                div.appendChild(valInput);
                div.appendChild(delBtn);

                tagsList.appendChild(div);
            }

            $("#existing-tags").show();
        }
    };
    getTagsRequest.send();
}

function sendTagsAsJson() {
    var tagsArray = [];
    var tags = document.getElementsByClassName("field-group");

    for(var i = 0; i < tags.length; i++) {
        var jsonParam = {};
        var key = tags.item(i).querySelectorAll('[name=key]')[0].value;
        var value = tags.item(i).querySelectorAll('[name=value]')[0].value;

        if (key.length > 0) {
            jsonParam["Key"] = key;
            jsonParam["Value"] = value;
            tagsArray.push(jsonParam);
        }
    }

    var xhr = new XMLHttpRequest();
    xhr.open("POST", baseUrl + "/do" + action + "/" + env + "/" + stack_name, true); //TODO update to region when region PR merged
    xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
    xhr.send(JSON.stringify(tagsArray));

    // Wait a mo for action to begin  in backend
    setTimeout(function () {
        // Redirect to action progress screen
        window.location = baseUrl + "/actionprogress/" + action + "/" + stack_name;
    }, 1000);
}