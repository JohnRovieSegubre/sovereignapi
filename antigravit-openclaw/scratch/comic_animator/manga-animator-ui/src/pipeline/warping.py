import cv2
import numpy as np
from typing import List, Dict, Tuple
from scipy.spatial import Delaunay

from ..config import PipelineConfig, default_config

class Warper:
    def __init__(self, config: PipelineConfig = default_config):
        self.config = config
        self.simplices = None  # Cache for Canonical Topology
        self.canonical_points = None
        self.corners = None

    def compute_topology(self, canonical_points: np.ndarray, image_shape: tuple) -> np.ndarray:
        """
        Computes the Delaunay triangulation once for the canonical pose (start frame).
        Includes corner points to ensure convex hull covers the image.
        """
        h, w = image_shape[:2]
        corners = np.array([
            [0, 0], [w-1, 0], [w-1, h-1], [0, h-1],
            [w//2, 0], [w//2, h-1], [0, h//2], [w-1, h//2]
        ])
        
        all_points = np.vstack([canonical_points, corners])
        tri = Delaunay(all_points)
        return tri.simplices, corners

    def warp_frame(self, 
                   source_image: np.ndarray, 
                   source_points: np.ndarray, 
                   target_points: np.ndarray,
                   reset_topology: bool = False) -> np.ndarray:
        """
        Warps the source_image using Fixed Topology (Mesh Locking).
        """
        if len(source_points) < 3:
            return source_image

        h, w = source_image.shape[:2]

        # 1. Topology Locking
        # If first frame or reset requested, compute topology based on SOURCE (Canonical)
        if self.simplices is None or reset_topology:
            self.simplices, self.corners = self.compute_topology(source_points, source_image.shape)
            self.canonical_points = source_points # Store reference if needed

        # 2. Add corners to current point sets
        # Corners are fixed (0 motion)
        all_source = np.vstack([source_points, self.corners])
        all_target = np.vstack([target_points, self.corners])

        # Output canvas
        warped_image = np.zeros_like(source_image)
        
        # 3. Render Triangles using Fixed Topology (self.simplices)
        for simplex in self.simplices:
            # simplex is indices [p1, p2, p3]
            img_dest = warped_image
            
            # Coordinates
            src_tri = all_source[simplex]
            dst_tri = all_target[simplex]
            
            # --- Affine Warp of Triangle ---
            
            # Bounding box of DESTINATION triangle
            r_dst = cv2.boundingRect(np.float32([dst_tri]))
            (x, y, w_tri, h_tri) = r_dst
            
            if w_tri <= 0 or h_tri <= 0: continue

            # Offset dst points to patch coordinates
            dst_tri_cropped = np.array([(pt[0] - x, pt[1] - y) for pt in dst_tri], np.float32)
            
            # Mask for the destination triangle
            mask = np.zeros((h_tri, w_tri), dtype=np.uint8)
            cv2.fillConvexPoly(mask, np.int32(dst_tri_cropped), (1, 1, 1), 16, 0)
            
            # Bounding box of SOURCE triangle
            r_src = cv2.boundingRect(np.float32([src_tri]))
            (x_src, y_src, w_src, h_src) = r_src
            
            if w_src <= 0 or h_src <= 0: continue

            # Crop source patch
            src_patch = source_image[y_src:y_src+h_src, x_src:x_src+w_src]
            
            # Offset src points to patch coordinates
            src_tri_patch = np.array([(pt[0] - x_src, pt[1] - y_src) for pt in src_tri], np.float32)

            # Compute Affine Transform: SRC Patch -> DST Patch
            try:
                M = cv2.getAffineTransform(src_tri_patch, dst_tri_cropped)
                
                # Warp
                warped_patch = cv2.warpAffine(src_patch, M, (w_tri, h_tri), 
                                            flags=cv2.INTER_LINEAR, 
                                            borderMode=cv2.BORDER_REFLECT_101)
                
                # Mask out pixels outside the triangle
                warped_patch = cv2.bitwise_and(warped_patch, warped_patch, mask=mask)
                
                # Compositing into Final Image
                dst_area = warped_image[y:y+h_tri, x:x+w_tri]
                
                # Clear destination area where we are checking
                # (1 where logic, 0 where bg)
                # We need to inverse mask to keep existing pixels
                dst_area_bg = cv2.bitwise_and(dst_area, dst_area, mask=cv2.bitwise_not(mask))
                
                final_patch = cv2.add(dst_area_bg, warped_patch)
                
                warped_image[y:y+h_tri, x:x+w_tri] = final_patch

            except Exception as e:
                # Fallback for degenerate triangles
                pass

        return warped_image
