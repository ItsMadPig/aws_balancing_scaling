#!/usr/bin/env python

###########################################
##Code by Aaron Hsu ahsu1@andrew.cmu.edu
##########################################
import boto.ec2
import time
import urllib2
import math
conn = boto.ec2.connect_to_region("us-east-1")

###########################
####constants
###########################
SECURITYGROUPNAME = "http_script"
SECURITYGROUPDESC = "http_via_script"
KEYNAME = '15319demo'
REGION = 'us-east-1a'
SUBNETID = "subnet-95b465be"
INSTTYPE = "m3.medium"
INTOK = 16

#######################################
###gets the instance object by the id
######################################
def getInstance(get_id, conn):
	reservations = conn.get_all_reservations()
	for instance in reservations:
		if instance.instances[0].id == get_id:
			return instance.instances[0]
	print(get_id)
	raise Exception("ID not found")

######################################################
#####gets the two strings representing the 
#####system_status and instance_status by the id
#####################################################
def getStatuses(get_id, conn):
	statuses = conn.get_all_instance_status()
	for instance in statuses:
		if instance.id == get_id:
			return (str(instance.system_status.status), str(instance.instance_status.status))
	print(get_id)
	raise Exception("Status not found")

#############################
####security group
#############################
#delete existing security group
#then creates a new one
def createSecurityGroup(conn):
	try:
		blah = conn.delete_security_group(SECURITYGROUPNAME)
		print(blah)
		print(SECURITYGROUPNAME + " deleted")
	except:
		print(SECURITYGROUPNAME + " cant be deleted")
	#create security group
	time.sleep(2)
	security = conn.create_security_group(
		SECURITYGROUPNAME,
		SECURITYGROUPDESC)
	time.sleep(2)
	#add rule
	authorized = security.authorize(
		ip_protocol="tcp",
		from_port=80,
		to_port=80,
		cidr_ip="0.0.0.0/0")
	print("Security group created and rules added")
	time.sleep(2)
	return

#######################################################
#####creates and returns load generator object and id
#######################################################
def createLoadGenerator(conn):

	load_temp = conn.run_instances(
		'ami-4c4e0f24',
		min_count=1,
		max_count=1,
		key_name= KEYNAME,
		security_groups=[SECURITYGROUPNAME],
		instance_type=INSTTYPE,
		placement= REGION)
	#	subnet_id= SUBNETID,
	time.sleep(10)
	print("load_temp = ",load_temp)
	load_inst = load_temp.instances[0]
	load_id = load_inst.id
	load_inst.add_tag("Project","2.1")
	return load_inst,load_id

######################################################
#####creates and returns data center object and id
######################################################
def createDataCenter(conn):	
	data_temp= conn.run_instances(
		'ami-b04106d8',
		min_count=1,
		max_count=1,
		key_name= KEYNAME,
		security_groups=[SECURITYGROUPNAME],
		instance_type=INSTTYPE,
		placement= REGION,
		monitoring_enabled=True)
	#	subnet_id= SUBNETID

	time.sleep(10)
	print("data_temp = ",data_temp)
	data_inst = data_temp.instances[0]
	data_id = data_inst.id
	data_inst.add_tag("Project","2.1")
	return data_inst,data_id

def main():
	createSecurityGroup(conn)
	(load_inst, load_id) = createLoadGenerator(conn)
	(data_inst, data_id) = createDataCenter(conn)
	print("INIT")
	print("---------------------------")
	print("load balancer= ",load_inst)
	print("data center= ", data_inst)
	print("load balancer state= ", load_inst.state_code, load_inst.state)
	print("data center state= ", data_inst.state_code, data_inst.state)
	print("")

	###########################################
	######check if running state
	###########################################
	lb_state = load_inst.state_code
	dc_state = data_inst.state_code
	while lb_state != INTOK or dc_state != INTOK:
		print("waiting for running state")
		print("lb_state= ",lb_state)
		print("dc_state= ",dc_state)
		time.sleep(10)

		load_inst = getInstance(load_id, conn)
		data_inst = getInstance(data_id, conn)
		lb_state = load_inst.state_code
		dc_state = data_inst.state_code

	print("instance states passed!")
	time.sleep(10)
	##############################################
	######check if one of sys or load status is OK
	##############################################
	#waiting for all OKs take too much time,
	#and not neccesary
	(load_system_status,load_instance_status) = getStatuses(load_id, conn)
	(data_system_status,data_instance_status) = getStatuses(data_id, conn)
	print("INIT")
	print("---------------------------")
	print("load_system_status= ", load_system_status, " load_insance_status= ",load_instance_status)
	print("data_system_status= ", data_system_status, " data_instance_status= ",data_instance_status)
	print("")

	while (load_system_status != "ok" and load_instance_status != "ok" and
		data_system_status != "ok" and data_instance_status != "ok"):
		print("waiting for Status:ok")
		print("load_system_status= ",load_system_status)
		print("load_instance_status= ",load_instance_status)
		print("data_system_status= ",data_system_status)
		print("data_instance_status= ",data_instance_status)
		time.sleep(10)
		(load_system_status,load_instance_status) = getStatuses(load_id, conn)
		(data_system_status,data_instance_status) = getStatuses(data_id, conn)

	print("system_status and instance_status ok!")
	print("load generator id= ", load_id)
	print("data center id= ", data_id)

	time.sleep(5)

	lb = getInstance(load_id,conn)
	dc = getInstance(data_id,conn)
	######################################
	######reads and gets testid
	######################################
	page1_content = urllib2.urlopen("http://"+lb.public_dns_name+"/test/horizontal?dns="+dc.public_dns_name).read()
	idxStart = page1_content.index("log?name=")
	idxEnd = page1_content.index(".log'>Test</a>")
	testID = page1_content[idxStart+9:idxEnd+4]
	print("testID= ",testID)
	time.sleep(2)


	######################################################
	######loop for checking logs and adding more databases
	######################################################
	numberDB = 1
	t0 = time.time()
	print ("time = ",t0)
	prev_content = urllib2.urlopen("http://"+lb.public_dns_name+"/log?name="+testID).read()
	while True:
		next_content = urllib2.urlopen("http://"+lb.public_dns_name+"/log?name="+testID).read()
		if prev_content != next_content:
			##################################################################
			#####if page has updated then read the lines,
			#####identifies by [Minute ,collects the rps until 
			#####there's another [Minute, if there is, then empty list
			#####if no more [Minute, then the rps collected must be the newest log
			####################################################################
			grepLines = urllib2.urlopen("http://"+lb.public_dns_name+"/log?name="+testID)
			lineList = []
			for line in grepLines:
				try:
					line.index("\n")
					moddedLine = line.split("\n")[0]
				except:
					moddedLine = line

				if moddedLine.find("[Minute") != -1:
					lineList = []
				elif moddedLine.find("ec2") != -1:
					idx = moddedLine.find(".com=")
					lineList.append(moddedLine[idx+5:])


			totalrps = float(0)
			if len(lineList) != numberDB:
				#sometimes after adding a new database, it doesnt reflect on
				#load balancer, so wait until log refreshes and shows all rps
				print("page hasnt reflected number of data centers")
				print("len of lineList= ",len(lineList))
				print("numberDB= ", numberDB)
				time.sleep(5)
				continue
			for rps in lineList:
				totalrps+= float(rps)
			print("totalrps = ",totalrps)
			if int(totalrps) < 4000:
				print (time.time() - t0)
				if int(time.time() - t0) > 100:
					#if time over 100 seconds and totalrps < 4000,
					#add more database
					print("adding more database...")
					(new_data_inst, new_data_id) = createDataCenter(conn)
					#waiting for running state
					new_dc_state = new_data_inst.state_code
					while new_dc_state != INTOK:
						print("waiting for running state")
						print("new_dc_state= ",new_dc_state)
						time.sleep(5)
						new_data_inst = getInstance(new_data_id, conn)
						new_dc_state = new_data_inst.state_code
					print("new data instance states passed!")
					time.sleep(5)

					(new_data_system_status,new_data_instance_status) = getStatuses(new_data_id, conn)
					print("new_data_system_status= ", new_data_system_status, " new_data_instance_status= ",new_data_instance_status)
					###########################################################################
					#####below code is for checking if one of status is ok, but takes too long,
					#####might exceed 30 minutes, thus simply waits for a minute.
					#####if no time restraint, best apply code below, time.sleep not reliable
					###########################################################################
					#while (new_data_system_status != "ok" and new_data_instance_status != "ok"):
					#	print("waiting for Status:ok")
					#	print("data_system_status= ",new_data_system_status)
					#	print("data_instance_status= ",new_data_instance_status)
					#	time.sleep(5)
					#	(new_data_system_status,new_data_instance_status) = getStatuses(new_data_id, conn)
					#print("new data center system_status and instance_status ok!")
					#time.sleep(5)
					time.sleep(60)

					added_content = urllib2.urlopen("http://"+lb.public_dns_name+"/test/horizontal/add?dns=" + new_data_inst.public_dns_name)
					numberDB+=1
					t0 = time.time()
				else:
					print("need to add more data but not yet 100 seconds")
			else:
				#if rps over 4000
				break

			prev_content = next_content
		else:
			#if page hasn't updated
			print("page hasn't refreshed")
			time.sleep(5)

main()