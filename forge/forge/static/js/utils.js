// JS helpers
function countOccurences(stringToSearch, searchTerm) {
    var count = 0;
    var position = stringToSearch.indexOf(searchTerm);
    while (position > -1) {
        ++count;
        position = stringToSearch.indexOf(searchTerm, ++position);
    }
    return count;
}

function removeElementsByClass(className){
    var elements = document.getElementsByClassName(className);
    while(elements.length > 0){
        elements[0].parentNode.removeChild(elements[0]);
    }
}

function notify(message) {
    if ("Notification" in window) {
        if (Notification.permission === "granted") {
            var notification = new Notification('Forge', {body: message, icon: '/static/img/Atlassian-vertical-blue@2x-rgb.png'});
        }
        else if (Notification.permission !== "denied") {
            Notification.requestPermission().then(function (permission) {
                if (permission === "granted") {
                    var notification = new Notification('Forge', {body: message, icon: '/static/img/Atlassian-vertical-blue@2x-rgb.png'});
                }
            });
        }
    }
}

// API helpers
function send_http_get_request(url, onreadystatechange, optionalFunctionParams) {
    var getRequest = new XMLHttpRequest();
    getRequest.open("GET", url, true);
    getRequest.setRequestHeader("Content-Type", "text/xml");
    getRequest.addEventListener("load", processResponse);
    if (onreadystatechange) {
        getRequest.onreadystatechange = function () {
            if (getRequest.readyState === XMLHttpRequest.DONE && getRequest.status === 200) {
                if (optionalFunctionParams)
                    onreadystatechange(getRequest.responseText, optionalFunctionParams);
                else
                    onreadystatechange(getRequest.responseText);
            }
        };
    }
    getRequest.send();
}

function send_http_post_request(url, data, onreadystatechange) {
    var postRequest = new XMLHttpRequest();
    postRequest.open("POST", url, true);
    postRequest.setRequestHeader("Content-Type", "application/json; charset=UTF-8");
    postRequest.addEventListener("load", processResponse);
    if (onreadystatechange) {
        postRequest.onreadystatechange = function () {
            if (postRequest.readyState === XMLHttpRequest.DONE && postRequest.status === 200)
                onreadystatechange(postRequest.responseText);
        };
    }
    postRequest.send(data);
}

// Create/modify page elements
function createDropdown(parameterKey, defaultValue, dropdownOptions, div) {
    var dropdownAnchor = document.createElement("A");
    dropdownAnchor.className = "aui-button aui-style-default aui-dropdown2-trigger";
    dropdownAnchor.setAttribute("aria-owns", parameterKey + "DropdownDiv");
    dropdownAnchor.setAttribute("aria-haspopup", "true");
    dropdownAnchor.setAttribute("href", "#" + parameterKey + "DropdownDiv");
    dropdownAnchor.id = parameterKey + "Val";
    if (defaultValue.length !== 0)
        dropdownAnchor.text = defaultValue;
    else
        dropdownAnchor.text = 'Select';

    var dropdownDiv = document.createElement("DIV");
    dropdownDiv.id = parameterKey + "DropdownDiv";
    dropdownDiv.className = "aui-style-default aui-dropdown2";

    var ul = document.createElement("UL");
    ul.className = "aui-list-truncate";

    for (var option in dropdownOptions) {
        var li = document.createElement("LI");
        var liAnchor = document.createElement("A");
        var text = document.createTextNode(dropdownOptions[option]);
        liAnchor.appendChild(text);
        liAnchor.addEventListener("click", function (data) {
            dropdownAnchor.text = data.target.text;

            // Set some smart defaults based on dropdown selections
            // TODO: remove these fields being toggled by TomcatSchemeVal; the fields were
            //       removed on 2018/11/19, but we don't want to break this functionality
            //       for older templates (yet), so targeting removal of these for Feb 2019.
            if (dropdownAnchor.id === "TomcatSchemeVal") {
                if (data.target.text === "https") {
                    updateTextField("TomcatProxyPort", "443");
                    updateTextField("TomcatSecure", "true");
                }
                else if (data.target.text === "http") {
                    updateTextField("TomcatProxyPort", "80");
                    updateTextField("TomcatSecure", "false");
                }
            } else if (dropdownAnchor.id === "VPCVal") {
                getSubnets(data.target.text, 'update');
            }
        }, false);
        li.appendChild(liAnchor);
        ul.appendChild(li);
    }
    dropdownDiv.appendChild(ul);
    div.append(dropdownAnchor);
    div.append(dropdownDiv);
}

function createMultiSelect(parameterKey, defaultValue, multiSelectOptions, div) {
    var multiSelect = document.createElement("SELECT");
    multiSelect.className = "multi-select";
    multiSelect.id = parameterKey + "Val";
    multiSelect.name = parameterKey + "Val";
    multiSelect.multiple = "multiple";
    multiSelect.size = "4";

    for (var opt in multiSelectOptions) {
        var option = document.createElement("OPTION");
        option.innerText = multiSelectOptions[opt];
        multiSelect.appendChild(option);
    }

    $("#" + parameterKey + "Val").remove();
    $(multiSelect).insertBefore($(div).children().last(), null);
}

function createInputParameter(param, fieldset) {
    var div = document.createElement("DIV");
    div.className = "field-group param-field-group";
    div.id = param.ParameterKey + "Div";
    div.name = "parameter";

    var label = document.createElement("LABEL");
    label.className = "paramLbl";
    label.htmlFor = param.ParameterKey + "Val";
    label.innerHTML = param.ParameterKey;
    div.appendChild(label);

    if (param.AllowedValues) {
        createDropdown(param.ParameterKey, param.ParameterValue, param['AllowedValues'], div);
    } else if (param.ParameterKey === "VPC") {
        if (action === 'clone')
            getVPCs($("#regionSelector").text().trim());
        else
            getVPCs(region, param.ParameterValue);
    } else {
        var input = document.createElement("INPUT");
        input.className = "text";
        input.id = param.ParameterKey + "Val";
        input.value = param.ParameterValue;

        if ((action === 'clone' || action === 'create')
            && (param.ParameterKey === "DBMasterUserPassword" || param.ParameterKey === "DBPassword")) {
            input.setAttribute("data-aui-validation-field", "");
            input.type = "password";
            input.value = "";
            input.required = true;
        } else if ((param.ParameterKey === "KeyName" || param.ParameterKey === "KeyPairName") && $("meta[name=ssh_key_name]").attr("value") !== "") {
            input.value = $("meta[name=ssh_key_name]").attr("value");
        } else if (param.ParameterKey === "HostedZone" && $("meta[name=hosted_zone]").attr("value") !== "") {
            input.value = $("meta[name=hosted_zone]").attr("value");
        }
        div.appendChild(input);
    }
    if (param.ParameterDescription) {
        var description = document.createElement("DIV");
        description.className = "description";
        description.innerText = param.ParameterDescription;
        div.appendChild(description);
    }
    fieldset.appendChild(div);
}

function updateMultiSelect(parameterKey, defaultValue, multiSelectOptions) {
    var multiSelect = document.getElementById(parameterKey + "Val");

    while (multiSelect.firstChild)
        multiSelect.removeChild(multiSelect.firstChild);

    for (var opt in multiSelectOptions) {
        var option = document.createElement("OPTION");
        option.innerText = multiSelectOptions[opt];
        multiSelect.appendChild(option);
    }
}

function updateTextField(parameterKey, newValue) {
    var textField = document.getElementById(parameterKey + "Val");

    if (textField) {
        textField.value = newValue;
    }
}

function addStackDropdown() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            selectStack(data.target.text);
        }, false);
    }
}

function addDefaultActionButtonListener() {
    var actionButton = document.getElementById("action-button");
    if (actionButton)
        actionButton.addEventListener("click", performAction);
}

// Forge common functions
function checkAuthenticated() {
    var stacks = document.getElementsByClassName("selectStackOption");
    if (stacks.length === 1 && stacks[0].text === 'No credentials') {
        AJS.flag({
            type: 'error',
            body: 'No credentials - please authenticate with Cloudtoken',
            close: 'manual'
        });
    }
}

function scrapePageForStackName() {
    var stack_name = $("#stackName").text();
    if (!stack_name) {
        stack_name = $("#StackNameVal").val();
    }
    return stack_name;
}

function getAuthDetailsAsJSON() {
    var username = $('#username').val();
    var password = $('#password').val();
    var jsonArray = [];
    var authDetails = {};
    authDetails["username"] = username;
    authDetails["password"] = password;
    jsonArray.push(authDetails);
    return jsonArray;
}

function redirectToLog(stack_name, extra_params) {
    // Wait a mo for action to begin  in backend
    setTimeout(function () {
        // Redirect to action progress screen
        var url = baseUrl + "/actionprogress/" + action + "?stack=" + stack_name;
        if (extra_params)
            url += extra_params;
        window.location = url;
    }, 1000);
}

function processResponse() {
    if (this.status !== 200) {
        window.location = baseUrl + "/error/" + this.status;
    }
}