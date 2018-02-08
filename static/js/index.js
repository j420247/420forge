
$(document).ready(function() {
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i ++) {
        stacks[i].addEventListener("click", function (data) {
            var stackName = data.target.text;
            $("#stackSelector").text(stackName);
            $("#upgradeVersionSelector").attr("aria-disabled", false);
        }, false);
    }

    var versions = document.getElementsByClassName("selectVersionOption");
    for (var i = 0; i < versions.length; i ++) {
        versions[i].addEventListener("click", function (data) {
            var stackName = data.target.text;
            $("#upgradeVersionSelector").text(stackName);
            $("#upgrade-button").attr("aria-disabled", false);
        }, false);
    }
});