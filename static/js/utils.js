function countOccurences(stringToSearch, searchTerm) {
    var count = 0;
    var position = stringToSearch.indexOf(searchTerm);
    while (position > -1) {
        ++count;
        position = stringToSearch.indexOf(searchTerm, ++position);
    }
    return count;
}

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
                getSubnets(region, data.target.text, true);
            }
        }, false);
        li.appendChild(liAnchor);
        ul.appendChild(li);
    }
    dropdownDiv.appendChild(ul);
    div.appendChild(dropdownAnchor);
    div.appendChild(dropdownDiv);
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

function checkAuthenticated() {
    var stacks = document.getElementsByClassName("selectStackOption");
    if (stacks.length == 1 && stacks[0].text == 'No credentials') {
        AJS.flag({
            type: 'error',
            body: 'No credentials - please authenticate with Cloudtoken',
            close: 'manual'
        });
    }
}

function notify(message) {
    if ("Notification" in window) {
        if (Notification.permission === "granted") {
            var notification = new Notification("Forge: " + message);
        }
        else if (Notification.permission !== "denied") {
            Notification.requestPermission().then(function (permission) {
                if (permission === "granted") {
                    var notification = new Notification("Forge: " + message);
                }
            });
        }
    }
}