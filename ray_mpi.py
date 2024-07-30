from mpi4py import MPI
import numpy as np
import matplotlib.pyplot as plt
#영상 생성을 위한 임포트
import os
from PIL import Image

# 벡터 정규화 함수
def normalize(vector):
    return vector / np.linalg.norm(vector)

# 벡터를 주어진 축에 대해 반사시키는 함수
def reflected(vector, axis):
    return vector - 2 * np.dot(vector, axis) * axis

# 구와의 교차점을 계산하는 함수
def sphere_intersect(center, radius, ray_origin, ray_direction):
    b = 2 * np.dot(ray_direction, ray_origin - center)
    c = np.linalg.norm(ray_origin - center) ** 2 - radius ** 2
    delta = b **2 - 4 * c
    if delta > 0:
        t1 = (-b + np.sqrt(delta)) / 2
        t2 = (-b - np.sqrt(delta)) / 2
        if t1 > 0 and t2 > 0:
            return min(t1, t2)
    return None

# 가장 가까운 교차점을 찾는 함수
def nearest_intersected_object(objects, ray_origin, ray_direction):
    distances = [sphere_intersect(obj['center'], obj['radius'], ray_origin, ray_direction) for obj in objects]
    nearest_object = None
    min_distance = np.inf
    for index, distance in enumerate(distances):
        if distance and distance < min_distance:
            min_distance = distance
            nearest_object = objects[index]
    return nearest_object, min_distance

# 레이 트레이싱 메인 함수
def ray_tracing(x, y):
    # 화면은 원점에 있음
    pixel = np.array([x, y, 0])
    origin = camera
    direction = normalize(pixel - origin)
    color = np.zeros((3))
    reflection = 1
    for k in range(max_depth):
        # 교차점 확인
        nearest_object, min_distance = nearest_intersected_object(objects, origin, direction)
        if nearest_object is None:
            break
        intersection = origin + min_distance * direction
        normal_to_surface = normalize(intersection - nearest_object['center'])
        shifted_point = intersection + 1e-5 * normal_to_surface
        intersection_to_light = normalize(light['position'] - shifted_point)
        _, min_distance = nearest_intersected_object(objects, shifted_point, intersection_to_light)
        intersection_to_light_distance = np.linalg.norm(light['position'] - intersection)
        is_shadowed = min_distance < intersection_to_light_distance
        if is_shadowed:
            break
        illumination = np.zeros((3))
        # 주변광
        illumination += nearest_object['ambient'] * light['ambient']
        # 확산광
        illumination += nearest_object['diffuse'] * light['diffuse'] * np.dot(intersection_to_light, normal_to_surface)
        # 반사광
        intersection_to_camera = normalize(camera - intersection)
        H = normalize(intersection_to_light + intersection_to_camera)
        illumination += nearest_object['specular'] * light['specular'] * np.dot(normal_to_surface, H) ** (nearest_object['shininess'] / 4)
        # 반사
        color += reflection * illumination
        reflection *= nearest_object['reflection']
        origin = shifted_point
        direction = reflected(direction, normal_to_surface)
    return color

# 프로그램 실행 시간 측정 시작
start_time = MPI.Wtime()

# 최대 반사 깊이
max_depth = 3

# 이미지 크기와 카메라 및 광원 설정
width = 600
height = 400
camera = np.array([0, 0, 1])
light = { 'position': np.array([5, 5, 5]), 'ambient': np.array([1, 1, 1]), 'diffuse': np.array([1, 1, 1]), 'specular': np.array([1, 1, 1]) }

# 씬에 있는 객체들 정의
objects = [
    { 'center': np.array([-0.2, 0, -1]), 'radius': 0.2, 'ambient': np.array([0.1, 0, 0]), 'diffuse': np.array([0.7, 1, 0]), 'specular': np.array([1, 1, 1]), 'shininess': 80, 'reflection': 0.1 },
    { 'center': np.array([0.1, -0.3, 0]), 'radius': 0.1, 'ambient': np.array([0.1, 0, 0.1]), 'diffuse': np.array([0.7, 0, 0.7]), 'specular': np.array([1, 1, 1]), 'shininess': 100, 'reflection': 0.5 },
    { 'center': np.array([0.5, 0, -1]), 'radius': 0.5, 'ambient': np.array([0.1, 0, 0.1]), 'diffuse': np.array([0.7, 0.7, 0.7]), 'specular': np.array([1, 1, 1]), 'shininess': 100, 'reflection': 0.5 },
    { 'center': np.array([-0.3, 0, 0]), 'radius': 0.15, 'ambient': np.array([0, 0.1, 0]), 'diffuse': np.array([0, 0.6, 0]), 'specular': np.array([1, 1, 1]), 'shininess': 100, 'reflection': 0.5 },
    { 'center': np.array([0, -9000, 0]), 'radius': 9000 - 0.7, 'ambient': np.array([0.1, 0.1, 0.1]), 'diffuse': np.array([0.6, 0.6, 0.6]), 'specular': np.array([1, 1, 1]), 'shininess': 100, 'reflection': 0.5 }
]


#기본 mpi변수들 선언
comm = MPI.COMM_WORLD
size = comm.Get_size()
rank = comm.Get_rank()

# 화면 비율과 스크린 크기 설정
ratio = float(width) / height 
screen = (-1, 1 / ratio, 1, -1 / ratio)
#count =0
image = np.empty([height, width, 3],dtype=float) if rank == 0 else None

N = height // size + int(height % size > rank)
start = comm.scan(N)-N

Y = np.linspace(screen[1], screen[3], height)[start:start+N]
X = np.linspace(screen[0], screen[2], width)

rank_image = np.zeros((N, width, 3))

for i, y in enumerate(Y):
    for j, x in enumerate(X):
        color = ray_tracing(x, y) 
        rank_image[i, j] = np.clip(color, 0, 1)

end_time = MPI.Wtime()
print(f"rank {rank}'s process is end at {int(end_time - start_time)} sec")

comm.Gather(rank_image,image)
if rank==0:
    # 결과 이미지를 파일로 저장
    plt.imsave(f'images/{count}.png', image)
    # 프로그램 실행 시간 측정 종료 (원본 파일의 시간 약 26초)
    all_end_time = MPI.Wtime()
    print(f"process {count + 1} is end at {all_end_time-start_time}")