from pandasdmx import Request
r = Request('ECB')
resp = r.get(resource_type = 'categoryscheme', agency = 'ESTAT', resource_id = 'all', 
             params=dict(references = 'all')) 

        
        