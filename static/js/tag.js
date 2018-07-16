var stack_name;

function onReady() {
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
}

function getTags() {
    var tagsList = document.getElementById("existing-tags");
    tagsList.innerHTML = "<h3>Existing tags</h3>";

    var getTagsRequest = new XMLHttpRequest();
    getTagsRequest.open("GET", baseUrl + "/getTags/" + region + "/" + stack_name, true);
    getTagsRequest.setRequestHeader("Content-Type", "text/xml");
    getTagsRequest.onreadystatechange = function () {
        if (getTagsRequest.readyState === XMLHttpRequest.DONE && getTagsRequest.status === 200) {
            tags = JSON.parse(getTagsRequest.responseText);

            // check for errors or no tags
            if (tags.length === 0) {
                var label = document.createElement("LABEL");
                label.innerText = "None";
                tagsList.appendChild(label);
                return;
            }
            if (tags[0].error) {
                var label = document.createElement("LABEL");
                label.innerText = tag[0].error;
                tagsList.appendChild(label);
                return;
            }

            // display each tag
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
                delBtn.addEventListener("click", function (data) {
                    var val = this.previousSibling;
                    var key = val.previousSibling;
                    if (key.style.getPropertyValue("text-decoration") !== "line-through") {
                        key.style.setProperty("text-decoration", "line-through");
                        key.disabled = true;
                        val.style.setProperty("text-decoration", "line-through");
                        val.disabled = true;
                        this.innerHTML = "<span class=\"aui-icon aui-icon-small aui-iconfont-undo\">Delete</span>";
                    } else {
                        key.style.removeProperty("text-decoration");
                        key.disabled = false;
                        val.style.removeProperty("text-decoration");
                        val.disabled = false;
                        this.innerHTML = "<span class=\"aui-icon aui-icon-small aui-iconfont-delete\">Delete</span>";
                    }
                });

                div.appendChild(keyInput);
                div.appendChild(valInput);
                div.appendChild(delBtn);

                tagsList.appendChild(div);
            }
        }
    };
    getTagsRequest.send();
}

function sendTagsAsJson() {
    var tagsArray = [];
    var tags = document.getElementsByClassName("field-group");

    for(var i = 0; i < tags.length; i++) {
        var jsonParam = {};

        var keyElement = tags.item(i).querySelectorAll('[name=key]')[0];
        var valElement = tags.item(i).querySelectorAll('[name=value]')[0];

        var key = keyElement.value;
        var value = valElement.value;

        if (key.length > 0 && keyElement.disabled === false) {
            jsonParam["Key"] = key;
            jsonParam["Value"] = value;
            tagsArray.push(jsonParam);
        }
    }

    var xhr = new XMLHttpRequest();
    xhr.open("POST", baseUrl + "/do" + action + "/" + region + "/" + stack_name, true);
    xhr.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
    xhr.send(JSON.stringify(tagsArray));

    // Wait a mo for action to begin  in backend
    setTimeout(function () {
        // Redirect to action progress screen
        window.location = baseUrl + "/actionprogress/" + action + "/" + stack_name;
    }, 1000);
}