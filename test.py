d = {}

k = 123

if not k in d.keys():
    d[k] = []

d[k].append({1:"123"})

print(d)
