// These values can be used to automatically populate template parameters
// This means you don't have to always copy/paste VPCs, subnets, hostedzones or ssh keys into the fields

// VPCs
// format vpc-56abc789
const us_east_1_default_vpc = "vpc-320c1355";
const us_west_2_default_vpc = "vpc-dd8dc7ba";
const lab_default_vpc = "vpc-ff1b9284";

// Subnets
// format 'subnet-12abc345,subnet-12abc346'
const us_east_1_default_subnets = "subnet-df0c3597,subnet-f1fb87ab";
const us_west_2_default_subnets = "subnet-eb952fa2,subnet-f2bddd95";
const lab_dmz_default_subnets = "subnet-a2b3a3c6,subnet-a9b08f86";
const lab_private_default_subnets = "subnet-d9162484,subnet-158d4b5f";

// Hosted Zone
// format 'myteam.example.com.'
const hosted_zone = "wpt.atlassian.com.";

// SSH Key
const ssh_key_name = "WPE-GenericKeyPair-20161102";