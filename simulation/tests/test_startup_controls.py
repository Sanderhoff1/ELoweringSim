"""Startup handover, live charger isolation and visible residual flux."""
from dataclasses import asdict
from types import SimpleNamespace
import unittest

from simulation.external_model import ExternalLoweringModel, reviewed_parameters
from simulation.energy_view import EnergyView


class Canvas:
    def __init__(self): self.items=[];self.bindings={};self.deletes=[]
    def bind(self,name,callback):self.bindings[name]=callback
    def winfo_width(self):return 985
    def winfo_height(self):return 634
    def configure(self,**kwargs):pass
    def delete(self,*args):
        self.deletes.append(args)
        if args == ('all',): self.items=[]
    def add(self,kind,args,options):
        self.items.append((kind,args,options));return len(self.items)
    def itemconfigure(self,item,**options):self.items[item-1][2].update(options)
    def coords(self,item,*args):
        kind,_,options=self.items[item-1];self.items[item-1]=(kind,args,options)
    def find_all(self):return tuple(range(1,len(self.items)+1))
    def create_text(self,*args,**options):return self.add('text',args,options)
    def create_line(self,*args,**options):return self.add('line',args,options)
    def create_oval(self,*args,**options):return self.add('oval',args,options)
    def create_rectangle(self,*args,**options):return self.add('rectangle',args,options)


class StartupControlsTests(unittest.TestCase):
    def balance(self,m):
        r=m.readings()
        self.assertLess(abs(r['energy_residual']),.002)
        self.assertLess(abs(r['power_diagnostics']['kcl']),2e-8)
        for name,c in r['power_diagnostics']['components'].items():
            self.assertLess(abs(c['residual']),2e-5,name)
        return r

    def test_capacitor_support_holds_until_field_qualifies_then_disconnects(self):
        m=ExternalLoweringModel()
        m.excitation_mode='capacitor';m.start_mode='external_supply';m.reset()
        initial=m.electrical.battery_energy
        for _ in range(50):m.step()
        r=self.balance(m)
        self.assertTrue(r['startup_support'])
        self.assertGreater(r['boost_power'],0)
        self.assertGreater(r['aux_energy'],0)
        self.assertEqual(r['capacitor_energy'],0)  # C_aux must become ready first.
        self.assertLess(m.electrical.battery_energy,initial)
        for _ in range(500):
            before=m.readings()['flux_magnitude']
            m.step()
            if m.support_complete:break
        self.assertTrue(m.support_complete)
        self.assertGreaterEqual(before,m.parameters.startup_flux_fraction*m.parameters.exciter_flux_target)
        self.assertGreaterEqual(m.support_qualified_time,m.parameters.startup_dwell)
        r=self.balance(m)
        self.assertGreater(r['boost_power'],0)  # Recharges C_aux after inverter handoff.
        self.assertEqual(r['inverter_current'],0)
        for _ in range(50):m.step()
        self.assertFalse(self.balance(m)['startup_support'])

    def test_insufficient_battery_cannot_fake_field_qualification(self):
        m=ExternalLoweringModel(reviewed_parameters(battery_initial_soc=0))
        m.excitation_mode='capacitor';m.start_mode='external_supply';m.reset()
        for _ in range(100):m.step()
        r=self.balance(m)
        self.assertFalse(m.support_complete)
        self.assertEqual(r['flux_magnitude'],0)
        self.assertEqual(r['boost_power'],0)

    def test_charger_click_changes_physics_without_reset(self):
        m=ExternalLoweringModel(reviewed_parameters(dc_initial_voltage=500,battery_initial_soc=50))
        m.inverter_enabled=False
        canvas=Canvas();view=EnergyView(canvas,lambda: self.fail('Wrong control toggled'))
        view.draw(m,m.readings(),[],False)
        snapshot=(asdict(m.state),asdict(m.electrical))
        click=SimpleNamespace(x=770*985/960,y=195*634/690)
        canvas.bindings['<Button-1>'](click)
        self.assertFalse(m.charger_enabled)
        self.assertEqual(snapshot,(asdict(m.state),asdict(m.electrical)))
        initial=m.electrical.battery_energy
        for _ in range(5):m.step()
        r=self.balance(m)
        self.assertEqual(r['charger_power'],0)
        self.assertGreater(r['battery_current'],0)  # Boost remains a separate live load.
        self.assertLess(m.electrical.battery_energy,initial)
        without_charger=m.electrical.battery_energy
        canvas.bindings['<Button-1>'](click)
        self.assertTrue(m.charger_enabled)
        m.step()
        r=self.balance(m)
        self.assertLess(r['charger_power'],0)
        self.assertGreater(m.electrical.battery_energy,without_charger)
        view.draw(m,r,[],False)
        self.assertIn('ON - click',[o.get('text') for _,_,o in canvas.items])

    def test_residual_field_is_visible_and_pause_is_stable(self):
        canvas=Canvas();view=EnergyView(canvas,lambda:None)
        zero=ExternalLoweringModel(reviewed_parameters(initial_flux=0))
        view.draw(zero,zero.readings(),[],False)
        zero_colors=[o['fill'] for kind,args,o in canvas.items if kind=='line' and len(args)==82]
        m=ExternalLoweringModel(reviewed_parameters(initial_flux=.005))
        r=m.readings();view.draw(m,r,[],False)
        texts=[o.get('text','') for _,_,o in canvas.items]
        self.assertTrue(any(f"{r['flux_magnitude']:.3g} Wb" in text for text in texts))
        self.assertNotIn('ZERO FIELD',texts)
        colors=[o['fill'] for kind,args,o in canvas.items if kind=='line' and len(args)==82]
        self.assertNotEqual(colors,zero_colors)
        frozen=list(canvas.items)
        view.draw(m,r,[],False)
        self.assertEqual(canvas.items,frozen)

    def test_energy_scene_is_persistent_between_frames(self):
        canvas=Canvas();view=EnergyView(canvas,lambda:None)
        m=ExternalLoweringModel()
        r=m.readings();view.draw(m,r,[],True)
        created=len(canvas.items)
        canvas.deletes.clear()
        r=m.readings();view.draw(m,r,[],True,visual_time=.016,update_text=False)
        self.assertEqual(len(canvas.items),created)
        self.assertNotIn(('all',),canvas.deletes)
        self.assertEqual(canvas.deletes,[])

    def test_energy_scene_names_every_topology_switch_and_brake_state(self):
        canvas=Canvas();view=EnergyView(canvas,lambda:None)
        m=ExternalLoweringModel();view.draw(m,m.readings(),[],False)
        text='\n'.join(o.get('text','') for _,_,o in canvas.items)
        for label in ('K_CAP','K_EXC','K_PRECHARGE','K_MAIN','BRAKE','APPLIED'):
            self.assertIn(label,text)

if __name__=='__main__':unittest.main()
