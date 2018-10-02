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
            if (dropdownAnchor.id === "TomcatSchemeVal") {
                if (data.target.text === "https") {
                    document.getElementById("TomcatProxyPortVal").value = "443";
                    document.getElementById("TomcatSecureVal").value = "true";
                }
                else if (data.target.text === "http") {
                    document.getElementById("TomcatProxyPortVal").value = "80";
                    document.getElementById("TomcatSecureVal").value = "false";
                }
            } else if (dropdownAnchor.id === "VPCVal") {
                if (data.target.text === us_east_1_default_vpc && us_east_1_default_subnets !== "") {
                    document.getElementById("ExternalSubnetsVal").value = us_east_1_default_subnets;
                    document.getElementById("InternalSubnetsVal").value = us_east_1_default_subnets;
                } else if (data.target.text === us_west_2_default_vpc && us_west_2_default_subnets !== "") {
                    document.getElementById("ExternalSubnetsVal").value = us_west_2_default_subnets;
                    document.getElementById("InternalSubnetsVal").value = us_west_2_default_subnets;
                }
            }
        }, false);
        li.appendChild(liAnchor);
        ul.appendChild(li);
    }
    dropdownDiv.appendChild(ul);
    div.appendChild(dropdownAnchor);
    div.appendChild(dropdownDiv);
}
