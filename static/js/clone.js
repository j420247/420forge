$(document).ready(function() {
    var regions = document.getElementsByClassName("selectRegionOption");
    for (var i = 0; i < regions.length; i++) {
        regions[i].addEventListener("click", function (data) {
            var region = data.target.text;
            $("#regionSelector").text(region);
            setSubnets(region);
        }, false);
    }
});

function setSubnets(region) {
    if (region === 'us-east-1') {
        document.getElementById("VPCVal").value = "vpc-320c1355";
        document.getElementById("ExternalSubnetsVal").value = "subnet-df0c3597,subnet-f1fb87ab";
        document.getElementById("InternalSubnetsVal").value = "subnet-df0c3597,subnet-f1fb87ab";
    }
    else if (region === 'us-west-2') {
        document.getElementById("VPCVal").value = "vpc-dd8dc7ba";
        document.getElementById("ExternalSubnetsVal").value = "subnet-eb952fa2,subnet-f2bddd95";
        document.getElementById("InternalSubnetsVal").value = "subnet-eb952fa2,subnet-f2bddd95";
    }
}