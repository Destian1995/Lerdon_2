"""Shared sprite footprints for midpoint placement, in any map scale."""
FEATURE_SIZE=68
PLACEMENT_GAP=10


def feature_rect(x,y,size=FEATURE_SIZE):
    return x-size/2,y-size*.38,x+size/2,y+size*.62


def separated(first,second,gap=PLACEMENT_GAP):
    return (first[2]+gap<=second[0] or second[2]+gap<=first[0] or
            first[3]+gap<=second[1] or second[3]+gap<=first[1])


class FeaturePlacementError(ValueError):
    pass
