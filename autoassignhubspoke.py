from airlinesim import ASInstance
ASI = ASInstance(183,'reality')
aircraftpool = ASI.getaircraftnumber(1006)#1006auto 1015xtra
departurepool = [735,825,1025,1225,1425,1625,1825,2010]
destA = ['SAN','LAX','PHX']
destB = ['BUR','LAS','DEN']
try:
    assert 2*len(departurepool) <= len(aircraftpool)
except AssertionError:
    departurepool = departurepool[:int(len(aircraftpool)/2)]

for departuretimeindex in range(len(departurepool)):
    print("assigning to :")
    print(destA)
    ASI.odhubspoke('SEA',destA,departurepool[departuretimeindex],aircraftpool[2*departuretimeindex])
    print("assigning to :")
    print(destB)
    ASI.odhubspoke('SEA',destB,departurepool[departuretimeindex],aircraftpool[2*departuretimeindex+1])

ASI.driver.close()
exit()