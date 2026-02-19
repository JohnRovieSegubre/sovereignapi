
import cv2
import numpy as np
from scipy.spatial import Delaunay
import matplotlib.pyplot as plt
from pathlib import Path

def generate_grid(rows=3, cols=3, scale=100):
    points = []
    for y in range(rows):
        for x in range(cols):
            points.append([x * scale, y * scale])
    return np.array(points, dtype=np.float32)

def visualize_mesh(img_shape, points, simplices, title, output_path):
    plt.figure(figsize=(5, 5))
    plt.title(title)
    plt.gca().invert_yaxis()
    
    # Plot edges
    for simplex in simplices:
        pts = points[simplex]
        # Close the loop
        pts = np.vstack([pts, pts[0]])
        plt.plot(pts[:, 0], pts[:, 1], 'b-', alpha=0.5)
        
    # Plot vertices
    plt.plot(points[:, 0], points[:, 1], 'ro')
    
    # Annotate indices
    for i, pt in enumerate(points):
        plt.text(pt[0], pt[1], str(i), fontsize=12)
        
    plt.savefig(output_path)
    plt.close()

def run_test():
    output_dir = Path("output/debug")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Canonical State (Start Frame)
    points_start = generate_grid(3, 3)
    # Center point is index 4 (in 3x3 grid)
    
    # Compute Canonical Topology
    tri = Delaunay(points_start)
    canonical_simplices = tri.simplices
    
    visualize_mesh((300, 300), points_start, canonical_simplices, 
                   "Frame 0 (Canonical)", output_dir / "topology_frame_0.png")

    # 2. Deformed State (End Frame)
    points_end = points_start.copy()
    # Move center point (4) significantly to the right, crossing index 5's vertical line
    points_end[4] = [210, 100] 
    
    # Scenario A: Adaptive Topology (What we had before)
    # Re-triangulate based on new positions
    tri_new = Delaunay(points_end)
    visualize_mesh((300, 300), points_end, tri_new.simplices, 
                   "Adaptive Topology (Flipping)", output_dir / "topology_adaptive.png")
                   
    # Scenario B: Locked Topology (The Fix)
    # Reuse canonical_simplices
    visualize_mesh((300, 300), points_end, canonical_simplices, 
                   "Locked Topology (Stable)", output_dir / "topology_locked.png")

    print(f"Test artifacts generated in {output_dir}")

if __name__ == "__main__":
    run_test()
