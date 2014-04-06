#
# Cookbook Name:: create-file
# Recipe:: default
#
# Copyright 2013, YOUR_COMPANY_NAME
#
# All rights reserved - Do Not Redistribute
#

cf = node['create_file']
f=cf['file_name']
contents = data_bag_item(cf['data_bag_name'], cf['data_bag_item'])[cf['data_bag_key']]

Chef::Log.warn("Will create file #{f}")

file f do
  owner "root"
  group "root"
  mode "0755"
  action :create
  content contents
end

