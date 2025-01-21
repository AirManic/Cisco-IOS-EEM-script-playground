import eem
import time

c = eem.env_reqinfo()

print("EEM Environment Variables")
for k, v in c.iteritems():
    print ("KEY : " + k + str(" ---> ") + v)

print ("Built in Variables")
for i, j in a.iteritems():
    print ("KEY : " + i + str(" ---> ") + j)
