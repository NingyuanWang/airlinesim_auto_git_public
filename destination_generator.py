import csv
import math
import cvxpy as cp
import numpy as np
import gurobipy
import random
curfewairportlist=['LGB','BUR','SAN','MSN','GRK','SNA','JAC','ISP','MKE','SJC','DCA','YUL']
curfewairportlist += ['NRT','HKD','YGJ','KMQ','NGS','SHB','KCZ','AXT','CTS','OKD','HND','SYO','FSZ','MBE','KUH','MMY','UKB','FUK','WKJ','AOJ','TSJ','OBO','OIT','KUM','KMI','SDJ','ISG','HIJ','MMB']
curfewairportlist += ['GMP','WLG','KHH','ADL','SYD','OOL','FRA','MUC','ORY']
curfewairportlist = set(curfewairportlist)
class Destination:
    'A Destionation consists of IATA code, distance, demand, etc. '
    def __init__(self,IATAcode,runwaylength,timezone,demand,distance,flightcount=0):
        self.IATAcode=IATAcode
        self.runwaylength = int(runwaylength)
        self.timezone = str(timezone)
        self.demand=int(demand)
        self.distance = float(distance)
        self.flightcount = int(flightcount)
class Intelligent_rotation_finder:
    def __init__(self,filename):
        self.destinationlist=[]
        csvfile=open(filename,'r')
        destchart = csv.reader(csvfile,csv.excel)
        for row in destchart:
            self.destinationlist.append(Destination(row[2],row[3],row[4],row[5],row[6]))
        csvfile.close()
    def findnextrotation(self,rotationcount,distancebound,departuretime_apprarent=0,turnaround_time=70.0,speed_in_minute=14.0,time_difference_in_minute=0):
        hour = int(departuretime_apprarent / 100)
        departuretime_in_minute = departuretime_apprarent - 40*hour
        rotation_IATA_list=[]
        distance_remaining = distancebound
        for rotation_index in range(1,rotationcount+1):
            best_destination_index=[-1,-1e6]
            for destination_index in range(len(self.destinationlist)):
                destination = self.destinationlist[destination_index]
                assert isinstance(destination,Destination)
                priority = priorityfunction(rotationcount-rotation_index,distance_remaining,destination)
                #Check curfew: 
                if (destination.IATAcode in curfewairportlist and not checkcurfewokay(destination.distance,departuretime_in_minute,speed_in_minute,time_difference_in_minute)):
                    priority = -1e7
                if priority > best_destination_index[1]:
                    best_destination_index[0] = destination_index
                    best_destination_index[1] = priority
            best_destination = self.destinationlist[best_destination_index[0]]
            distance_remaining -= best_destination.distance
            if best_destination_index[0] < 0:
                break
            rotation_IATA_list.append(best_destination.IATAcode)

            departuretime_in_minute = approx_next_hub_departure(departuretime_in_minute,best_destination.distance,turnaround_time,speed_in_minute)
            self.destinationlist[best_destination_index[0]].flightcount += 1
            print("next distination: "+best_destination.IATAcode+", distance: "+str(best_destination.distance))

        return rotation_IATA_list
class Integer_programming_rotation_finder:
    def __init__(self,filename):
        self.destinationlist=[]
        csvfile=open(filename,'r')
        destchart = csv.reader(csvfile,csv.excel)
        for row in destchart:
            self.destinationlist.append(Destination(row[2],row[3],row[4],row[5],row[6]))
        csvfile.close()
    def __translateline(self,line):
        returnIATAlist = []
        distancesum=0.0
        for i in range(len(self.destinationlist)):
            if line[i]>0.8:
                returnIATAlist.append(self.destinationlist[i].IATAcode)
                distancesum += self.destinationlist[i].distance
        return returnIATAlist
    def __updateflightcount(self,line):
        for i in range(len(self.destinationlist)):
            if line[i]>0.8:
                self.destinationlist[i].flightcount += 1
    def find_next_rotation(self,rotationcount,distancebound):
        #not stable in the sense throwing infeasible even though obviously feasible somewhere
        destinationcount=len(self.destinationlist)
        distance_list = np.array([row.distance for row in self.destinationlist])
        weight_list=np.array([math.exp(0.3*row.demand) * math.exp(-0.0003*row.distance) / (0.5+row.flightcount) for row in self.destinationlist])
        destination_factor_vect = np.multiply(distance_list+300, weight_list)
        A = cp.Variable(destinationcount,boolean=True)
        objective_function=cp.Maximize(A*destination_factor_vect)
        rotation_constraint=[A*np.ones(destinationcount)<=rotationcount,A*distance_list<=distancebound]
        ip_problem = cp.Problem(objective_function,rotation_constraint)      
        ip_problem.solve(solver=cp.GUROBI)
        print(ip_problem.status)
        optimal_rotation_line = A.value
        self.__updateflightcount(optimal_rotation_line)
        return self.__translateline(optimal_rotation_line)
    def adjust_existing_rotation(self,destIATA,existing_rotation):
        for row in self.destinationlist:
            if row.IATAcode==destIATA:
                row.flightcount += existing_rotation
    def find_rotations(self,aircraftcount,rotationcount,distancebound):
        rotation_list = []
        #iterate through number of aircrafts: 
        destinationcount=len(self.destinationlist)
        distance_list = np.array([row.distance for row in self.destinationlist])
        A = cp.Variable(destinationcount,boolean=True)
        b = cp.Parameter(destinationcount)
        objective_function=cp.Maximize(A*b)
        rotation_constraint=[A*np.ones(destinationcount)<=rotationcount + 0.1,A*distance_list<=distancebound]
        ip_problem = cp.Problem(objective_function,rotation_constraint)
        for i in range(aircraftcount):
            weight_list=np.array([math.exp(0.3*row.demand) * math.exp(-0.0003*row.distance) / (0.5+row.flightcount) for row in self.destinationlist])
            destination_factor_vect = np.multiply(distance_list+300, weight_list)
            b.value = destination_factor_vect
            ip_problem.solve(solver=cp.GUROBI)
            optimal_rotation_line = A.value
            print(ip_problem.status)
            self.__updateflightcount(optimal_rotation_line)
            rotation = self.__translateline(optimal_rotation_line)
            rotation_list.append(rotation)
            print(rotation)
            print("Total distance:",sum([self.find_distance(destIATA) for destIATA in rotation]))
        return rotation_list
    def find_departure_time(self,rotation,turnaround_time=70.0,speed_in_minute=14.0,time_difference_in_minute=0):
        #returns a valid departure time for given rotation, or a negative number if not possible
        departure_time = 0
        for i in range(100):
            departure_time = random.randint(300,580)#Was 0,1430
            if self.validate_departure_time(rotation,departure_time,turnaround_time,speed_in_minute,time_difference_in_minute):
                departure_time_apparant = int(departure_time/60) * 40 + departure_time
                return departure_time_apparant
        return -1
        
        
    def find_distance(self,destIATA):
        distance_list = [row.distance for row in self.destinationlist if row.IATAcode==destIATA]
        distance = distance_list[0]
        return distance
    def validate_departure_time(self,rotation,departure_time,turnaround_time=70.0,speed_in_minute=14.0,time_difference_in_minute=0):
        current_time = departure_time
        for airportIATA in rotation:
            distance = self.find_distance(airportIATA)
            if (airportIATA in curfewairportlist and not checkcurfewokay(distance,current_time,speed_in_minute,time_difference_in_minute)):
                return False
            current_time = approx_next_hub_departure(current_time,distance,turnaround_time,speed_in_minute)
        return True


def approx_next_hub_departure(current_time,distance,turnaround_time=70.0,speed_in_minute=14.0):
    rotation_time = 2*(25+turnaround_time + distance/speed_in_minute)
    next_departure_time = current_time + rotation_time
    if next_departure_time > 24*60:
        next_departure_time -= 24*60
    return next_departure_time
def checkcurfewokay(distance,departure_time_in_minute,speed_in_minute=14.0,time_difference_in_minute=0):
    #For time difference: value is positive when headquater timezone is ahead of destination timezone
    #Also, not implemented yet
    curfew_minutes_lb = 6*60
    curfew_minutes_ub = 22*60+40
    flight_time = 25+distance/float(speed_in_minute)
    arrival_time = flight_time+departure_time_in_minute
    if arrival_time > 24*60:
        arrival_time -= 24*60
    if arrival_time>curfew_minutes_ub:
        return False
    if arrival_time<curfew_minutes_lb:
        return False
    return True
def priorityfunction(count_remaining,distance_remaining,destination,avg_dist_factor=50.0):
    assert isinstance(destination,Destination)
    if destination.distance>distance_remaining:
        return -1e7
    avg_distance = distance_remaining / (1+count_remaining)
    destination_weight = math.exp(0.35*destination.demand) * math.exp(-0.00025*destination.distance)
    distance_deviation_penalty=avg_dist_factor*math.pow((avg_distance - destination.distance)/avg_distance,2)/math.pow(0.3+count_remaining,2.0)
    return (-distance_deviation_penalty + destination_weight)/(1+destination.flightcount)
def main():
    iprf = Integer_programming_rotation_finder('DEN_dest_list.csv')
    iprf.adjust_existing_rotation('COS',20)
    print(iprf.find_rotations(10,3,4500))
    
    
    iprf.find_rotations(1,3,4400)
   

if __name__ == '__main__':
    main()