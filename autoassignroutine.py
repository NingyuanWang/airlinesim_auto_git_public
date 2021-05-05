from airlinesim import ASInstance
ASI = ASInstance(183,'reality')
aircraftpool = ASI.getaircraftnumber('autoassign')
departure = [230,350,505,725]
dest = ['IAD','IAD','BHM','FAR','SJC','SAN']
for i in range(len(aircraftpool)):
	ASI.odflightshuttle('ORD',dest[i],departure[i],4,aircraftpool[i])
ASI.driver.close()
exit()