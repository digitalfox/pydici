insert into crm_subsidiary select * from core_subsidiary;
insert into crm_company select * from crm_clientcompany;
insert into crm_contact select * from crm_clientcontact;
create table crm_businessbroker_backup as select * from crm_businessbroker;
