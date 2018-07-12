-- From https://bulldogwiki.internal.atlassian.com/wiki/display/~nhdang/SQL+queries+for+EAC-stg+post-sync

-- Update banners to remove customized content in EAC prod and warn people this is stg.
update bandana set bandanavalue=regexp_replace(bandanavalue, '<afterBodyStart>.*</afterBodyStart>', '<afterBodyStart>&lt;div class=&quot;aui-message info&quot;&gt;&#x0D;
   &lt;span class=&quot;aui-icon icon-info&quot;&gt;&lt;/span&gt;&#x0D;
   &lt;p&gt;This is a QA copy of EAC.  Its content is regularly overwritten with the content of EAC. &lt;br&gt;If you are testing it, please put up the testing banner with your name &lt;a href=&quot;https://extranet.stg.internal.atlassian.com/admin/editcustomhtml.action&quot;&gt;here&lt;/a&gt;&lt;/p&gt;&#x0D;
&lt;/div&gt;&#x0D;
&#x0D;
&lt;!--&#x0D;
&lt;div class=&quot;aui-message warning&quot;&gt;&#x0D;
   &lt;span class=&quot;aui-icon icon-warning&quot;&gt;&lt;/span&gt;&#x0D;
   &lt;p&gt;QA-CAC is currently being tested by &lt;strong&gt;Insert tester name here&lt;/strong&gt;. Please no not update this site until this banner is removed&lt;/p&gt;&#x0D;
&lt;/div&gt;&#x0D;
--&gt;</afterBodyStart>') where bandanacontext = '_GLOBAL' and bandanakey = 'atlassian.confluence.settings';
update bandana set bandanavalue=regexp_replace(bandanavalue, '<beforeBodyEnd>.*</beforeBodyEnd>', '<beforeBodyEnd></beforeBodyEnd>') where bandanacontext = '_GLOBAL' and bandanakey = 'atlassian.confluence.settings';

-- Update baseUrl
update bandana set bandanavalue=regexp_replace(bandanavalue, '<baseUrl>.*</baseUrl>', '<baseUrl>https://extranet.stg.internal.atlassian.com</baseUrl>') where bandanacontext = '_GLOBAL' and bandanakey = 'atlassian.confluence.settings';

-- Disable trackback
update bandana set bandanavalue=regexp_replace(bandanavalue, '<allowTrackbacks>.*</allowTrackbacks>', '<allowTrackbacks>false</allowTrackbacks>') where bandanacontext = '_GLOBAL' and bandanakey = 'atlassian.confluence.settings';

-- update the Server ID : ADM-22077
UPDATE bandana SET bandanavalue = '<string>BCLG-2HEF-I71O-3O1I</string>' WHERE bandanakey = 'confluence.server.id';

-- update SAML config
UPDATE bandana SET bandanavalue = '<string>-----BEGIN CERTIFICATE-----
MIIDkTCCAnmgAwIBAgIQRmUJYc4XVrtIdQ/deNbn6zANBgkqhkiG9w0BAQsFADAk
MSIwIAYDVQQDDBlDZW50cmlmeSBDdXN0b21lciBBQVMwNjQxMB4XDTE3MDYxMzAz
MzI1OVoXDTM5MDEwMTAwMDAwMFowRDFCMEAGA1UEAww5Q2VudHJpZnkgQ3VzdG9t
ZXIgQUFTMDY0MSBBcHBsaWNhdGlvbiBTaWduaW5nIENlcnRpZmljYXRlMIIBIjAN
BgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoYIV3rOdKXnGCwA3MBj7EYwP5GJr
U+jHbTDTJL16fpu5bs8gAR3eWLuuCUBc5PhItJzAljBV69qVWCmP2cZ7QgNKUl4Q
p9yqmNUO7UmBhM3Xi6c/88jpNiPBvJYTX+Qab7Xm3XqDp1C91PnLETyYxrP56bp2
+bMbXWXE8TL7p1YLTvsa38b9p+ISvsnV4RUEV581oeA+X6utuw3ae5I9E3rUDlEX
rzd7uaWCDRv6GjWSSYsecfUE6wCy2ONmQzDNRttFKU+PaMZvDkUezKgkchusnNrm
Vq0HBR3SrNmCfbqiXPclDSZOad/ZS3sscF8AnraXOx1zXYz76jdRRVhvgwIDAQAB
o4GeMIGbMBMGCisGAQQBgqZwAQkEBQwDMS4wMBcGCisGAQQBgqZwAQMECQwHQUFT
MDY0MTAfBgNVHSMEGDAWgBT/YwHKfWflaSo7rU4FcXfQ9WzynzAdBgNVHQ4EFgQU
V2D9gNOSENQJYMOOPvLKVRaaJ0gwDgYDVR0PAQH/BAQDAgWgMBsGCisGAQQBgqZw
AQQEDQwLQXBwbGljYXRpb24wDQYJKoZIhvcNAQELBQADggEBADF24/ct+BOaLkWT
tWKLM7nG+N/3y77TVxeKyhTT8xl4no5QmalioAaxE0txXs1QH3ffqcGBfGDvrSJQ
Wid0ALotFmSTvpdoHFc5JQUZpw2P76Dy1//EY5YmgirqhT2ERlUOstZyOJEwKIPn
Zm3sTDh84e+uABpxxjTFIAByiPrcxwbns4dit2nLYQoUF7sAzqmwnyWrwVf+KgKH
CiCGu51wSZ/T5Wk1bJxTeTUiFiM7oX2q4oG0742I4S838+UCzwcYRy6TCLqxUZan
+PJvnutIEX3+GVWWpv4CjelOSqKiRLRmQ5g8bAZforCclcIT1gHAhtiSDxR0rNso
FDMypMU=
-----END CERTIFICATE-----
</string>'
 WHERE bandanakey = 'com.atlassian.plugins.authentication.samlconfig.signing-cert';

UPDATE bandana SET bandanavalue = '<string>https://aas0641.my.centrify.com/f681a7b2-0c99-4c08-9eee-21fb05c7d76a</string>'
 WHERE bandanakey = 'com.atlassian.plugins.authentication.samlconfig.sso-issuer';

UPDATE bandana SET bandanavalue = '<string>https://aas0641.my.centrify.com/applogin/appKey/f681a7b2-0c99-4c08-9eee-21fb05c7d76a/customerId/AAS0641</string>'
 WHERE bandanakey = 'com.atlassian.plugins.authentication.samlconfig.sso-url';

-- update Synchrony config so appid is regenerated for staging on startup
DELETE from bandana WHERE bandanakey='synchrony_collaborative_editor_app_id' AND bandanacontext='_GLOBAL';
DELETE from bandana WHERE bandanakey='synchrony_collaborative_editor_app_registered' AND bandanacontext='_GLOBAL';

-- add confluence-administrators
--
-- Seriously dodgy hack alert:
--
-- Swiped from the QA-JAC post-sync cleanup script
--
-- The plpgsql language is required, which must be enabled by a sysadmin:
-- CREATE LANGUAGE plpgsql;
--
-- FIXME: this should really take a list of users, and add each one to the
-- group if they're not already in it.
-- However, I don't think plpgsql has an easy way of supplying an arbitrarily
-- long list of strings as an argument.
-- CREATE LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION add_admin_users(role varchar(64), username varchar(64)) RETURNS void AS \$\$
DECLARE
    directoryid bigint := id FROM cwd_directory WHERE directory_type = 'INTERNAL';
    userid bigint := id FROM cwd_user WHERE user_name = username AND directory_id = directoryid;
    groupid bigint := id FROM cwd_group WHERE group_name = role AND directory_id = directoryid;
    membershipid bigint := MAX(id) + 1 FROM cwd_membership;
BEGIN
    IF EXISTS (SELECT id FROM cwd_membership WHERE parent_id = groupid AND child_user_id = userid)
    THEN
        NULL;
    ELSE
        INSERT INTO cwd_membership (id, parent_id, child_group_id, child_user_id)
            VALUES (membershipid, groupid, NULL, userid);
    END IF;
END
-- \$\$ LANGUAGE plpgsql;
-- End seriously dodgy hack alert

-- Add smoke test account - ADM-44531 refers
SELECT add_admin_users('confluence-administrators', 'testuser1');

-- re-enable bogus admin user for sanity tests
update cwd_user set active = 'T' where id = 1870856280;
update cwd_user_attribute set   attribute_value = '0' where attribute_name = 'invalidPasswordAttempts' and user_id = 1870856280;
update cwd_user_attribute set   attribute_lower_value = '0' where attribute_name = 'invalidPasswordAttempts' and user_id = 1870856280;
update logininfo set curfailed = 0 where username = '2c9082c93f36441c013f364a7e74001a';
update cwd_user set credential = '{PKCS5S2}QbOQRweYgQXOy7QZWwKGhaQ0yyAClaLJ06lSDyuwXtq2O98WAZeX56b/pe+5348Q' where id = 1870856280;
delete from cwd_membership where id=1870856280;
insert into cwd_membership (id, parent_id, child_user_id) values ((select id from cwd_user where user_name='admin'), (select id from cwd_group where group_name='confluence-users' and directory_id=(select id from cwd_directory where directory_name='Confluence Internal Directory')), (select id from cwd_user where user_name='admin'));
SELECT add_admin_users('confluence-administrators', 'admin');