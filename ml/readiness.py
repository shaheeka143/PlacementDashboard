def calculate_readiness(skill, resume):
    interview = int((skill + resume) / 2)
    readiness = int(0.5 * skill + 0.3 * resume + 0.2 * interview)
    return interview, readiness
