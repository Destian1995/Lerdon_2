"""Check actual animation art, alpha, coverage and Android atlas dimensions."""
import hashlib
import json
from pathlib import Path
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]/'files/army/animated'
STATES={'idle','walk','attack','hit','death'}


class UnitSpriteAssetTests(unittest.TestCase):
    def test_idle_registration_covers_every_character_and_preserves_first_pose(self):
        registry=json.loads((ROOT/'index.json').read_text(encoding='utf-8'))
        for relative in registry['characters'].values():
            data=json.loads((ROOT/relative).read_text(encoding='utf-8'))
            registration=data['idle_registration']
            self.assertEqual(registration['shifts'][0],[0,0])
            frames=data['animations']['idle']['frames']
            base=frames[0]['offset']
            self.assertEqual(len(frames),len(registration['shifts']))
            for frame,(dx,dy) in zip(frames,registration['shifts']):
                self.assertEqual(frame['offset'],[base[0]+dx,base[1]+dy])

    def test_frost_idle_silhouette_stays_in_place_across_the_loop_boundary(self):
        data=json.loads((ROOT/'vampires/frost.json').read_text(encoding='utf-8'))
        centers=[]
        with Image.open(ROOT/'vampires/frost.png') as image:
            for frame in data['animations']['idle']['frames']:
                x,y,w,h=frame['rect']
                alpha=image.crop((x,y,x+w,y+h)).getchannel('A')
                masses=list(alpha.resize((w,1),Image.Resampling.BOX).tobytes())
                center=sum(i*mass for i,mass in enumerate(masses))/sum(masses)
                centers.append(center-frame['offset'][0])
        # Previously the figure drifted 26 pixels and jumped back every second.
        self.assertLess(max(centers)-min(centers),3)
        self.assertLess(abs(centers[-1]-centers[0]),3)

    def test_complete_roster_has_all_five_actions_without_missing_or_opaque_sheets(self):
        registry=json.loads((ROOT/'index.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(registry['characters']),73)
        self.assertGreaterEqual(len(registry['references']),len(registry['characters']))
        for key,relative in registry['characters'].items():
            with self.subTest(character=key):
                path=ROOT/relative;data=json.loads(path.read_text(encoding='utf-8'))
                image_path=path.parent/data['image']
                self.assertEqual(hashlib.sha256(image_path.read_bytes()).hexdigest(),data['sha256'])
                with Image.open(image_path) as image:
                    self.assertEqual(image.mode,'RGBA')
                    self.assertLessEqual(max(image.size),2048)
                    histogram=image.getchannel('A').histogram()
                    self.assertGreater(sum(histogram[:11])/(image.width*image.height),.4)
                    self.assertEqual(set(data['animations'])-{'melee'},STATES)
                    self.assertEqual(registry['references'][data['reference']],key)
                    for state,clip in data['animations'].items():
                        if clip.get('image'):continue  # Separate supplemental atlases are verified below.
                        self.assertEqual(len(clip['frames']),6)
                        self.assertGreater(clip['fps'],0)
                        self.assertEqual(clip['loop'],state in ('idle','walk'))
                        drawings=set()
                        for frame in clip['frames']:
                            x,y,w,h=frame['rect']
                            self.assertGreater(w,0);self.assertEqual(w,h)
                            self.assertGreaterEqual(min(x,y),0)
                            self.assertLessEqual(x+w,image.width);self.assertLessEqual(y+h,image.height)
                            cut=image.crop((x,y,x+w,y+h))
                            alpha=cut.getchannel('A')
                            self.assertIsNotNone(alpha.point(lambda a:255 if a>48 else 0).getbbox())
                            edges=(alpha.crop((0,0,1,h)),alpha.crop((w-1,0,w,h)),
                                   alpha.crop((0,0,w,1)),alpha.crop((0,h-1,w,h)))
                            self.assertLess(max(sum(edge.histogram()[240:]) for edge in edges),8,
                                            (key,state,'opaque figure touches cell edge'))
                            drawings.add(hashlib.sha256(cut.tobytes()).digest())
                        self.assertEqual(len(drawings),6,(key,state,'duplicate drawn frames'))

    def test_melee_supplements_are_complete_and_match_existing_idle_scale(self):
        from tools.package_melee_sprites import bounds
        expected={'north-hunter','north/vlad','elves/archer','undead/archer',
                  'elines/blood-mage','elves/priestess','elves/disease',
                  'undead/banshee','undead/morgana'}
        registry=json.loads((ROOT/'index.json').read_text(encoding='utf-8'))
        found=set()
        for key,relative in registry['characters'].items():
            path=ROOT/relative;data=json.loads(path.read_text(encoding='utf-8'))
            clip=data['animations'].get('melee')
            if not clip or not clip.get('image'):continue
            found.add(key)
            extra=path.parent/clip['image']
            self.assertEqual(hashlib.sha256(extra.read_bytes()).hexdigest(),clip['sha256'])
            self.assertFalse(clip['loop']);self.assertEqual(len(clip['frames']),6)
            with Image.open(path.parent/data['image']) as original,Image.open(extra) as image:
                self.assertEqual(image.mode,'RGBA');self.assertLessEqual(max(image.size),2048)
                idle=data['animations']['idle']['frames'][0]
                box,root= bounds(original,idle['rect'])
                target_height=(box[3]-box[1])/data['frame_size'][1]
                target_root=root/data['frame_size'][0]-data['ground_anchor'][0]-idle['offset'][0]/data['frame_size'][0]
                target_ground=1-box[3]/data['frame_size'][1]-data['ground_anchor'][1]+idle['offset'][1]/data['frame_size'][1]
                first,_=bounds(image,clip['frames'][0]['rect'])
                height=(first[3]-first[1])/clip['frame_size'][1]*clip['scale']
                self.assertAlmostEqual(height,target_height,places=5)
                drawings=set()
                for frame in clip['frames']:
                    x,y,w,h=frame['rect']
                    self.assertGreaterEqual(min(x,y),0)
                    self.assertLessEqual(x+w,image.width);self.assertLessEqual(y+h,image.height)
                    box,root=bounds(image,frame['rect'])
                    root_position=(root/w-clip['ground_anchor'][0]-frame['offset'][0]/w)*clip['scale']
                    ground=(1-box[3]/h-clip['ground_anchor'][1]+frame['offset'][1]/h)*clip['scale']
                    self.assertAlmostEqual(root_position,target_root,places=4)
                    self.assertAlmostEqual(ground,target_ground,places=4)
                    cut=image.crop((x,y,x+w,y+h));drawings.add(hashlib.sha256(cut.tobytes()).hexdigest())
                    alpha=cut.getchannel('A')
                    self.assertIsNotNone(alpha.point(lambda a:255 if a>48 else 0).getbbox())
                    edges=(alpha.crop((0,0,1,h)),alpha.crop((w-1,0,w,h)),
                           alpha.crop((0,0,w,1)),alpha.crop((0,h-1,w,h)))
                    self.assertLess(max(sum(edge.histogram()[240:]) for edge in edges),8,(key,frame['rect']))
                self.assertEqual(len(drawings),6,key)
        self.assertEqual(found,expected)
