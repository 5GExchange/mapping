import json
import matplotlib.pyplot as plt

with open('requests.json') as data_file:
    requests = json.load(data_file)
    

#Create mapped picture
x=[]
for i in xrange(0,len(requests['mapped_requests'])):
    x.append(i)

plt.plot(x,requests['mapped_requests'])
plt.title('Mapped requests')
plt.show()

"""
#Running mapped picture
x=[]
for i in xrange(0,len(requests['mapped_requests'])):
    x.append(i)

plt.plot(x,requests['mapped_requests'])
plt.title('Mapped requests')
plt.show()


#Create mapped picture
x=[]
for i in xrange(0,len(requests['mapped_requests'])):
    x.append(i)

plt.plot(x,requests['mapped_requests'])
plt.title('Mapped requests')
plt.show()
"""